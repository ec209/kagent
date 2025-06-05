package autogen

import (
	"context"
	"encoding/json"
	"fmt"
	"reflect"
	"strings"
	"sync"

	"github.com/hashicorp/go-multierror"
	"github.com/kagent-dev/kagent/go/autogen/api"
	"k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

	autogen_client "github.com/kagent-dev/kagent/go/autogen/client"
	"github.com/kagent-dev/kagent/go/controller/api/v1alpha1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

var (
	reconcileLog = ctrl.Log.WithName("reconcile")
)

type AutogenReconciler interface {
	ReconcileAutogenAgent(ctx context.Context, req ctrl.Request) error
	ReconcileAutogenModelConfig(ctx context.Context, req ctrl.Request) error
	ReconcileAutogenTeam(ctx context.Context, req ctrl.Request) error
	ReconcileAutogenApiKeySecret(ctx context.Context, req ctrl.Request) error
	ReconcileAutogenToolServer(ctx context.Context, req ctrl.Request) error
	ReconcileAutogenMemory(ctx context.Context, req ctrl.Request) error
}

type autogenReconciler struct {
	translator ApiTranslator

	kube          client.Client
	autogenClient *autogen_client.Client

	defaultModelConfig types.NamespacedName
	upsertLock         sync.Mutex
}

func NewAutogenReconciler(
	translator ApiTranslator,
	kube client.Client,
	autogenClient *autogen_client.Client,
	defaultModelConfig types.NamespacedName,
) AutogenReconciler {
	return &autogenReconciler{
		translator:         translator,
		kube:               kube,
		autogenClient:      autogenClient,
		defaultModelConfig: defaultModelConfig,
	}
}

func (a *autogenReconciler) ReconcileAutogenAgent(ctx context.Context, req ctrl.Request) error {
	agent := &v1alpha1.Agent{}
	if err := a.kube.Get(ctx, req.NamespacedName, agent); err != nil {
		if errors.IsNotFound(err) {
			return a.handleAgentDeletion(req)
		}
		return fmt.Errorf("failed to get agent %s/%s: %w", req.Namespace, req.Name, err)
	}

	return a.handleExistingAgent(ctx, agent, req)
}

func (a *autogenReconciler) handleAgentDeletion(req ctrl.Request) error {
	team, err := a.autogenClient.GetTeam(req.Name, GlobalUserID)
	if err != nil {
		return fmt.Errorf("failed to get agent on deletion %s/%s: %w", req.Namespace, req.Name, err)
	}

	if team != nil {
		if err = a.autogenClient.DeleteTeam(team.Id, team.UserID); err != nil {
			return fmt.Errorf("failed to delete agent %s/%s: %w", req.Namespace, req.Name, err)
		}
	}

	return nil
}

func (a *autogenReconciler) handleExistingAgent(ctx context.Context, agent *v1alpha1.Agent, req ctrl.Request) error {
	if err := a.reconcileAgents(ctx, agent); err != nil {
		return fmt.Errorf("failed to reconcile agent %s/%s: %w", req.Namespace, req.Name, err)
	}

	teams, err := a.findTeamsUsingAgent(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to find teams for agent %s/%s: %w", req.Namespace, req.Name, err)
	}

	return a.reconcileAgentStatus(ctx, agent, a.reconcileTeams(ctx, teams...))
}

func (a *autogenReconciler) reconcileAgentStatus(ctx context.Context, agent *v1alpha1.Agent, err error) error {
	status := metav1.ConditionTrue
	reason := "AgentReconciled"
	message := ""

	if err != nil {
		status = metav1.ConditionFalse
		message = err.Error()
		reason = "AgentReconcileFailed"
	}

	conditionChanged := meta.SetStatusCondition(&agent.Status.Conditions, metav1.Condition{
		Type:               v1alpha1.AgentConditionTypeAccepted,
		Status:             status,
		LastTransitionTime: metav1.Now(),
		Reason:             reason,
		Message:            message,
	})

	if conditionChanged || agent.Status.ObservedGeneration != agent.Generation {
		agent.Status.ObservedGeneration = agent.Generation
		if err := a.kube.Status().Update(ctx, agent); err != nil {
			return fmt.Errorf("failed to update agent status: %v", err)
		}
	}
	return nil
}

func (a *autogenReconciler) ReconcileAutogenModelConfig(ctx context.Context, req ctrl.Request) error {
	modelConfig := &v1alpha1.ModelConfig{}
	if err := a.kube.Get(ctx, req.NamespacedName, modelConfig); err != nil {
		if errors.IsNotFound(err) {
			reconcileLog.Info("ModelConfig deleted", "modelConfig", req.Name)
			return nil
		}
		return fmt.Errorf("failed to get model %s: %v", req.Name, err)
	}

	// Handle finalizer for secret cleanup
	const finalizerName = "modelconfig.kagent.dev/secret-cleanup"
	if modelConfig.DeletionTimestamp != nil {
		// ModelConfig is being deleted, clean up secrets
		if err := a.handleModelConfigDeletion(ctx, modelConfig, finalizerName); err != nil {
			return err
		}
		return nil
	}

	// Add finalizer if not present
	if !hasFinalizer(modelConfig.Finalizers, finalizerName) {
		modelConfig.Finalizers = append(modelConfig.Finalizers, finalizerName)
		if err := a.kube.Update(ctx, modelConfig); err != nil {
			return fmt.Errorf("failed to add finalizer: %v", err)
		}
	}

	// If this is a Bedrock model, ensure the kagent deployment has access to the secret
	if modelConfig.Spec.Provider == v1alpha1.Bedrock {
		if err := a.reconcileKagentDeploymentForBedrock(ctx, modelConfig); err != nil {
			return fmt.Errorf("failed to reconcile kagent deployment for Bedrock: %v", err)
		}
	}

	agents, err := a.findAgentsUsingModel(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to find agents for model %s: %v", req.Name, err)
	}

	if err := a.reconcileAgents(ctx, agents...); err != nil {
		return fmt.Errorf("failed to reconcile agents for model %s: %v", req.Name, err)
	}

	teams, err := a.findTeamsUsingModel(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to find teams for model %s: %v", req.Name, err)
	}

	return a.reconcileModelConfigStatus(
		ctx,
		modelConfig,
		a.reconcileTeams(ctx, teams...),
	)
}

// reconcileKagentDeploymentForBedrock ensures the kagent deployment can access Bedrock secrets
func (a *autogenReconciler) reconcileKagentDeploymentForBedrock(ctx context.Context, modelConfig *v1alpha1.ModelConfig) error {
	// Since we're now using LiteLLM SDK directly in the app container,
	// we don't need to mount secrets to a separate LiteLLM container.
	// The app will read credentials dynamically from secrets at request time.
	reconcileLog.Info("Bedrock model configured for direct SDK access",
		"model", modelConfig.Name,
		"secretRef", modelConfig.Spec.APIKeySecretRef)

	return nil
}

// handleModelConfigDeletion cleans up secrets when a ModelConfig is deleted
func (a *autogenReconciler) handleModelConfigDeletion(ctx context.Context, modelConfig *v1alpha1.ModelConfig, finalizerName string) error {
	// Delete the associated secret
	if modelConfig.Spec.APIKeySecretRef != "" {
		secret := &corev1.Secret{}
		secretName := types.NamespacedName{
			Name:      modelConfig.Spec.APIKeySecretRef,
			Namespace: modelConfig.Namespace,
		}

		if err := a.kube.Get(ctx, secretName, secret); err != nil {
			if !errors.IsNotFound(err) {
				return fmt.Errorf("failed to get secret %s: %v", secretName.Name, err)
			}
			// Secret already deleted, nothing to do
		} else {
			if err := a.kube.Delete(ctx, secret); err != nil {
				return fmt.Errorf("failed to delete secret %s: %v", secretName.Name, err)
			}
			reconcileLog.Info("Deleted secret for ModelConfig", "modelConfig", modelConfig.Name, "secret", secretName.Name)
		}
	}

	// Remove finalizer
	modelConfig.Finalizers = removeFinalizer(modelConfig.Finalizers, finalizerName)
	if err := a.kube.Update(ctx, modelConfig); err != nil {
		return fmt.Errorf("failed to remove finalizer: %v", err)
	}

	return nil
}

// hasFinalizer checks if a finalizer exists in the list
func hasFinalizer(finalizers []string, finalizer string) bool {
	for _, f := range finalizers {
		if f == finalizer {
			return true
		}
	}
	return false
}

// removeFinalizer removes a finalizer from the list
func removeFinalizer(finalizers []string, finalizer string) []string {
	var result []string
	for _, f := range finalizers {
		if f != finalizer {
			result = append(result, f)
		}
	}
	return result
}

func (a *autogenReconciler) reconcileModelConfigStatus(ctx context.Context, modelConfig *v1alpha1.ModelConfig, err error) error {
	status := metav1.ConditionTrue
	reason := "ModelConfigReconciled"
	message := ""

	if err != nil {
		status = metav1.ConditionFalse
		message = err.Error()
		reason = "ModelConfigReconcileFailed"
	}

	conditionChanged := meta.SetStatusCondition(&modelConfig.Status.Conditions, metav1.Condition{
		Type:               v1alpha1.ModelConfigConditionTypeAccepted,
		Status:             status,
		LastTransitionTime: metav1.Now(),
		Reason:             reason,
		Message:            message,
	})

	if conditionChanged || modelConfig.Status.ObservedGeneration != modelConfig.Generation {
		modelConfig.Status.ObservedGeneration = modelConfig.Generation
		if err := a.kube.Status().Update(ctx, modelConfig); err != nil {
			return fmt.Errorf("failed to update model config status: %v", err)
		}
	}
	return nil
}

func (a *autogenReconciler) ReconcileAutogenTeam(ctx context.Context, req ctrl.Request) error {
	team := &v1alpha1.Team{}
	if err := a.kube.Get(ctx, req.NamespacedName, team); err != nil {
		return fmt.Errorf("failed to get team %s: %v", req.Name, err)
	}

	return a.reconcileTeamStatus(ctx, team, a.reconcileTeams(ctx, team))
}

func (a *autogenReconciler) reconcileTeamStatus(ctx context.Context, team *v1alpha1.Team, err error) error {
	status := metav1.ConditionTrue
	reason := "TeamReconciled"
	message := ""

	if err != nil {
		status = metav1.ConditionFalse
		message = err.Error()
		reason = "TeamReconcileFailed"
	}

	conditionChanged := meta.SetStatusCondition(&team.Status.Conditions, metav1.Condition{
		Type:               v1alpha1.TeamConditionTypeAccepted,
		Status:             status,
		LastTransitionTime: metav1.Now(),
		Reason:             reason,
		Message:            message,
	})

	if conditionChanged || team.Status.ObservedGeneration != team.Generation {
		team.Status.ObservedGeneration = team.Generation
		if err := a.kube.Status().Update(ctx, team); err != nil {
			return fmt.Errorf("failed to update team status: %v", err)
		}
	}

	return nil
}

func (a *autogenReconciler) ReconcileAutogenApiKeySecret(ctx context.Context, req ctrl.Request) error {
	agents, err := a.findAgentsUsingApiKeySecret(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to find agents for secret %s: %v", req.Name, err)
	}

	if err := a.reconcileAgents(ctx, agents...); err != nil {
		return fmt.Errorf("failed to reconcile agents for secret %s: %v", req.Name, err)
	}

	teams, err := a.findTeamsUsingApiKeySecret(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to find teams for api key secret %s: %v", req.Name, err)
	}

	return a.reconcileTeams(ctx, teams...)
}

func (a *autogenReconciler) ReconcileAutogenToolServer(ctx context.Context, req ctrl.Request) error {
	toolServer := &v1alpha1.ToolServer{}
	if err := a.kube.Get(ctx, req.NamespacedName, toolServer); err != nil {
		if errors.IsNotFound(err) {
			return nil
		}
		return fmt.Errorf("failed to get tool server %s: %v", req.Name, err)
	}

	serverID, reconcileErr := a.reconcileToolServer(ctx, toolServer)

	if err := a.reconcileToolServerStatus(ctx, toolServer, serverID, reconcileErr); err != nil {
		return fmt.Errorf("failed to reconcile tool server %s: %v", req.Name, err)
	}

	agents, err := a.findAgentsUsingToolServer(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to find agents for tool server %s: %v", req.Name, err)
	}

	return a.reconcileAgents(ctx, agents...)
}

func (a *autogenReconciler) reconcileToolServerStatus(
	ctx context.Context,
	toolServer *v1alpha1.ToolServer,
	serverID int,
	err error,
) error {
	discoveredTools, discoveryErr := a.getDiscoveredMCPTools(serverID)
	if discoveryErr != nil {
		err = multierror.Append(err, discoveryErr)
	}

	status := metav1.ConditionTrue
	reason := "ToolServerReconciled"
	message := ""

	if err != nil {
		status = metav1.ConditionFalse
		message = err.Error()
		reason = "ToolServerReconcileFailed"
	}

	conditionChanged := meta.SetStatusCondition(&toolServer.Status.Conditions, metav1.Condition{
		Type:               v1alpha1.AgentConditionTypeAccepted,
		Status:             status,
		LastTransitionTime: metav1.Now(),
		Reason:             reason,
		Message:            message,
	})

	if !conditionChanged &&
		toolServer.Status.ObservedGeneration == toolServer.Generation &&
		reflect.DeepEqual(toolServer.Status.DiscoveredTools, discoveredTools) {
		return nil
	}

	toolServer.Status.ObservedGeneration = toolServer.Generation
	toolServer.Status.DiscoveredTools = discoveredTools

	if err := a.kube.Status().Update(ctx, toolServer); err != nil {
		return fmt.Errorf("failed to update tool server status: %v", err)
	}

	return nil
}

func (a *autogenReconciler) ReconcileAutogenMemory(ctx context.Context, req ctrl.Request) error {
	memory := &v1alpha1.Memory{}
	if err := a.kube.Get(ctx, req.NamespacedName, memory); err != nil {
		return fmt.Errorf("failed to get memory %s: %v", req.Name, err)
	}

	agents, err := a.findAgentsUsingMemory(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to find agents using memory %s: %v", req.Name, err)
	}

	return a.reconcileMemoryStatus(ctx, memory, a.reconcileAgents(ctx, agents...))
}

func (a *autogenReconciler) reconcileMemoryStatus(ctx context.Context, memory *v1alpha1.Memory, err error) error {
	status := metav1.ConditionTrue
	reason := "MemoryReconciled"
	message := ""

	if err != nil {
		status = metav1.ConditionFalse
		message = err.Error()
		reason = "MemoryReconcileFailed"
	}

	conditionChanged := meta.SetStatusCondition(&memory.Status.Conditions, metav1.Condition{
		Type:               v1alpha1.MemoryConditionTypeAccepted,
		Status:             status,
		LastTransitionTime: metav1.Now(),
		Reason:             reason,
		Message:            message,
	})

	if conditionChanged || memory.Status.ObservedGeneration != memory.Generation {
		memory.Status.ObservedGeneration = memory.Generation
		if err := a.kube.Status().Update(ctx, memory); err != nil {
			return fmt.Errorf("failed to update memory status: %v", err)
		}
	}
	return nil
}

func (a *autogenReconciler) reconcileTeams(ctx context.Context, teams ...*v1alpha1.Team) error {
	errs := map[types.NamespacedName]error{}
	for _, team := range teams {
		autogenTeam, err := a.translator.TranslateGroupChatForTeam(ctx, team)
		if err != nil {
			errs[types.NamespacedName{Name: team.Name, Namespace: team.Namespace}] = fmt.Errorf("failed to translate team %s: %v", team.Name, err)
			continue
		}
		if err := a.upsertTeam(autogenTeam); err != nil {
			errs[types.NamespacedName{Name: team.Name, Namespace: team.Namespace}] = fmt.Errorf("failed to upsert team %s: %v", team.Name, err)
			continue
		}
	}

	if len(errs) > 0 {
		return fmt.Errorf("failed to reconcile teams: %v", errs)
	}

	return nil
}

func (a *autogenReconciler) reconcileAgents(ctx context.Context, agents ...*v1alpha1.Agent) error {
	errs := map[types.NamespacedName]error{}
	for _, agent := range agents {
		autogenTeam, err := a.translator.TranslateGroupChatForAgent(ctx, agent)
		if err != nil {
			errs[types.NamespacedName{Name: agent.Name, Namespace: agent.Namespace}] = fmt.Errorf("failed to translate agent %s: %v", agent.Name, err)
			continue
		}
		if err := a.upsertTeam(autogenTeam); err != nil {
			errs[types.NamespacedName{Name: agent.Name, Namespace: agent.Namespace}] = fmt.Errorf("failed to upsert agent %s: %v", agent.Name, err)
			continue
		}
	}

	if len(errs) > 0 {
		return fmt.Errorf("failed to reconcile agents: %v", errs)
	}

	return nil
}

func (a *autogenReconciler) reconcileToolServer(ctx context.Context, server *v1alpha1.ToolServer) (int, error) {
	toolServer, err := a.translator.TranslateToolServer(ctx, server)
	if err != nil {
		return 0, fmt.Errorf("failed to translate tool server %s: %v", server.Name, err)
	}
	serverID, err := a.upsertToolServer(toolServer)
	if err != nil {
		return 0, fmt.Errorf("failed to upsert tool server %s: %v", server.Name, err)
	}

	return serverID, nil
}

func (a *autogenReconciler) upsertTeam(team *autogen_client.Team) error {
	// lock to prevent races
	a.upsertLock.Lock()
	defer a.upsertLock.Unlock()
	// validate the team
	req := autogen_client.ValidationRequest{
		Component: team.Component,
	}
	resp, err := a.autogenClient.Validate(&req)
	if err != nil {
		return fmt.Errorf("failed to validate team %s: %v", team.Component.Label, err)
	}
	if !resp.IsValid {
		return fmt.Errorf("team %s is invalid: %v", team.Component.Label, resp.ErrorMsg())
	}

	// delete if team exists
	existingTeam, err := a.autogenClient.GetTeam(team.Component.Label, GlobalUserID)
	if err != nil {
		return fmt.Errorf("failed to get existing team %s: %v", team.Component.Label, err)
	}
	if existingTeam != nil {
		team.Id = existingTeam.Id
	}

	return a.autogenClient.CreateTeam(team)
}

func (a *autogenReconciler) upsertToolServer(toolServer *autogen_client.ToolServer) (int, error) {
	// lock to prevent races
	a.upsertLock.Lock()
	defer a.upsertLock.Unlock()

	// delete if toolServer exists
	existingToolServer, err := a.autogenClient.GetToolServerByLabel(toolServer.Component.Label, GlobalUserID)
	if err != nil && !strings.Contains(err.Error(), "not found") {
		return 0, fmt.Errorf("failed to get existing toolServer %s: %v", toolServer.Component.Label, err)
	}
	if existingToolServer != nil {
		toolServer.Id = existingToolServer.Id
		err = a.autogenClient.UpdateToolServer(toolServer, GlobalUserID)
		if err != nil {
			return 0, fmt.Errorf("failed to delete existing toolServer %s: %v", toolServer.Component.Label, err)
		}
	} else {
		existingToolServer, err = a.autogenClient.CreateToolServer(toolServer, GlobalUserID)
		if err != nil {
			return 0, fmt.Errorf("failed to create toolServer %s: %v", toolServer.Component.Label, err)
		}
		existingToolServer, err = a.autogenClient.GetToolServerByLabel(toolServer.Component.Label, GlobalUserID)
		if err != nil {
			return 0, fmt.Errorf("failed to get existing toolServer %s: %v", toolServer.Component.Label, err)
		}
	}

	err = a.autogenClient.RefreshToolServer(existingToolServer.Id, GlobalUserID)
	if err != nil {
		return 0, fmt.Errorf("failed to refresh toolServer %s: %v", toolServer.Component.Label, err)
	}

	return existingToolServer.Id, nil
}

func (a *autogenReconciler) findAgentsUsingModel(ctx context.Context, req ctrl.Request) ([]*v1alpha1.Agent, error) {
	var agentsList v1alpha1.AgentList
	if err := a.kube.List(
		ctx,
		&agentsList,
		client.InNamespace(req.Namespace),
	); err != nil {
		return nil, fmt.Errorf("failed to list agents: %v", err)
	}

	var agents []*v1alpha1.Agent
	for i := range agentsList.Items {
		agent := &agentsList.Items[i]
		if getRefFromString(agent.Spec.ModelConfig, agent.Namespace) == req.NamespacedName {
			agents = append(agents, agent)
		}
	}

	return agents, nil
}

func (a *autogenReconciler) findAgentsUsingApiKeySecret(ctx context.Context, req ctrl.Request) ([]*v1alpha1.Agent, error) {
	var modelsList v1alpha1.ModelConfigList
	if err := a.kube.List(
		ctx,
		&modelsList,
		client.InNamespace(req.Namespace),
	); err != nil {
		return nil, fmt.Errorf("failed to list model configs: %v", err)
	}

	var models []string
	for _, model := range modelsList.Items {
		if getRefFromString(model.Spec.APIKeySecretRef, model.Namespace) == req.NamespacedName {
			models = append(models, model.Name)
		}
	}

	var agents []*v1alpha1.Agent
	uniqueAgents := make(map[string]bool)

	for _, modelName := range models {
		agentsUsingModel, err := a.findAgentsUsingModel(ctx, ctrl.Request{
			NamespacedName: types.NamespacedName{
				Namespace: req.Namespace,
				Name:      modelName,
			},
		})
		if err != nil {
			return nil, fmt.Errorf("failed to find agents for model %s: %v", modelName, err)
		}

		for _, agent := range agentsUsingModel {
			key := fmt.Sprintf("%s/%s", agent.Namespace, agent.Name)
			if !uniqueAgents[key] {
				uniqueAgents[key] = true
				agents = append(agents, agent)
			}
		}
	}

	return agents, nil
}

func (a *autogenReconciler) findAgentsUsingMemory(ctx context.Context, req ctrl.Request) ([]*v1alpha1.Agent, error) {
	var agentsList v1alpha1.AgentList
	if err := a.kube.List(
		ctx,
		&agentsList,
		client.InNamespace(req.Namespace),
	); err != nil {
		return nil, fmt.Errorf("failed to list agents: %v", err)
	}

	var agents []*v1alpha1.Agent
	for i := range agentsList.Items {
		agent := &agentsList.Items[i]
		for _, memory := range agent.Spec.Memory {
			if getRefFromString(memory, agent.Namespace) == req.NamespacedName {
				agents = append(agents, agent)
				break
			}
		}
	}

	return agents, nil
}

func (a *autogenReconciler) findTeamsUsingAgent(ctx context.Context, req ctrl.Request) ([]*v1alpha1.Team, error) {
	var teamsList v1alpha1.TeamList
	if err := a.kube.List(
		ctx,
		&teamsList,
		client.InNamespace(req.Namespace),
	); err != nil {
		return nil, fmt.Errorf("failed to list teams: %v", err)
	}

	var teams []*v1alpha1.Team
	for i := range teamsList.Items {
		team := &teamsList.Items[i]
		for _, participant := range team.Spec.Participants {
			if getRefFromString(participant, team.Namespace) == req.NamespacedName {
				teams = append(teams, team)
				break
			}
		}
	}

	return teams, nil
}

func (a *autogenReconciler) findTeamsUsingModel(ctx context.Context, req ctrl.Request) ([]*v1alpha1.Team, error) {
	var teamsList v1alpha1.TeamList
	if err := a.kube.List(
		ctx,
		&teamsList,
		client.InNamespace(req.Namespace),
	); err != nil {
		return nil, fmt.Errorf("failed to list teams: %v", err)
	}

	var teams []*v1alpha1.Team
	for i := range teamsList.Items {
		team := &teamsList.Items[i]
		if getRefFromString(team.Spec.ModelConfig, team.Namespace) == req.NamespacedName {
			teams = append(teams, team)
		}
	}

	return teams, nil
}

func (a *autogenReconciler) findTeamsUsingApiKeySecret(ctx context.Context, req ctrl.Request) ([]*v1alpha1.Team, error) {
	var modelsList v1alpha1.ModelConfigList
	if err := a.kube.List(
		ctx,
		&modelsList,
		client.InNamespace(req.Namespace),
	); err != nil {
		return nil, fmt.Errorf("failed to list model configs: %v", err)
	}

	var models []string
	for _, model := range modelsList.Items {
		if getRefFromString(model.Spec.APIKeySecretRef, model.Namespace) == req.NamespacedName {
			models = append(models, model.Name)
		}
	}

	var teams []*v1alpha1.Team
	uniqueTeams := make(map[string]bool)

	for _, modelName := range models {
		teamsUsingModel, err := a.findTeamsUsingModel(ctx, ctrl.Request{
			NamespacedName: types.NamespacedName{
				Namespace: req.Namespace,
				Name:      modelName,
			},
		})
		if err != nil {
			return nil, fmt.Errorf("failed to find teams for model %s: %v", modelName, err)
		}

		for _, team := range teamsUsingModel {
			key := fmt.Sprintf("%s/%s", team.Namespace, team.Name)
			if !uniqueTeams[key] {
				uniqueTeams[key] = true
				teams = append(teams, team)
			}
		}
	}

	return teams, nil
}

func (a *autogenReconciler) findAgentsUsingToolServer(ctx context.Context, req ctrl.Request) ([]*v1alpha1.Agent, error) {
	var agentsList v1alpha1.AgentList
	if err := a.kube.List(
		ctx,
		&agentsList,
		client.InNamespace(req.Namespace),
	); err != nil {
		return nil, fmt.Errorf("failed to list agents: %v", err)
	}

	var agents []*v1alpha1.Agent
	appendAgentIfUsesToolServer := func(agent *v1alpha1.Agent) {
		for _, tool := range agent.Spec.Tools {
			if tool.McpServer != nil && getRefFromString(tool.McpServer.ToolServer, agent.Namespace) == req.NamespacedName {
				agents = append(agents, agent)
				return
			}
		}
	}

	for _, agent := range agentsList.Items {
		agent := agent
		appendAgentIfUsesToolServer(&agent)
	}

	return agents, nil
}

func (a *autogenReconciler) getDiscoveredMCPTools(serverID int) ([]*v1alpha1.MCPTool, error) {
	allTools, err := a.autogenClient.ListTools(GlobalUserID)
	if err != nil {
		return nil, err
	}

	var discoveredTools []*v1alpha1.MCPTool
	for _, tool := range allTools {
		if tool.ServerID != nil && *tool.ServerID == serverID {
			mcpTool, err := convertTool(tool)
			if err != nil {
				return nil, fmt.Errorf("failed to convert tool: %v", err)
			}
			discoveredTools = append(discoveredTools, mcpTool)
		}
	}

	return discoveredTools, nil
}

func convertTool(tool *autogen_client.Tool) (*v1alpha1.MCPTool, error) {
	if tool.Component == nil || tool.Component.Config == nil {
		return nil, fmt.Errorf("missing component or config")
	}
	config := tool.Component.Config
	var mcpToolConfig api.MCPToolConfig
	if err := unmarshalFromMap(config, &mcpToolConfig); err != nil {
		return nil, fmt.Errorf("failed to unmarshal tool config: %v", err)
	}
	component, err := convertComponentToApiType(tool.Component)
	if err != nil {
		return nil, fmt.Errorf("failed to convert component: %v", err)
	}

	return &v1alpha1.MCPTool{
		Name:      mcpToolConfig.Tool.Name,
		Component: component,
	}, nil
}

func convertComponentToApiType(component *api.Component) (v1alpha1.Component, error) {
	anyConfig, err := convertMapToAnytype(component.Config)
	if err != nil {
		return v1alpha1.Component{}, err
	}
	return v1alpha1.Component{
		Provider:         component.Provider,
		ComponentType:    component.ComponentType,
		Version:          component.Version,
		ComponentVersion: component.ComponentVersion,
		Description:      component.Description,
		Label:            component.Label,
		Config:           anyConfig,
	}, nil
}

func convertMapToAnytype(m map[string]interface{}) (map[string]v1alpha1.AnyType, error) {
	anyConfig := make(map[string]v1alpha1.AnyType)
	for k, v := range m {
		b, err := json.Marshal(v)
		if err != nil {
			return nil, err
		}
		anyConfig[k] = v1alpha1.AnyType{
			RawMessage: b,
		}
	}
	return anyConfig, nil
}

func unmarshalFromMap(m map[string]interface{}, v interface{}) error {
	b, err := json.Marshal(m)
	if err != nil {
		return err
	}
	return json.Unmarshal(b, v)
}
