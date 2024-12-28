from hyperbolic_agentkit_core.actions.deploy_validator_node import (
    DeployValidatorNodeAction,
)
from hyperbolic_agentkit_core.actions.get_available_gpus import GetAvailableGpusAction
from hyperbolic_agentkit_core.actions.get_gpu_status import GetGpuStatusAction
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.remote_shell import RemoteShellAction
from hyperbolic_agentkit_core.actions.get_spend_history import GetSpendHistoryAction
from hyperbolic_agentkit_core.actions.terminate_compute import TerminateComputeAction
from hyperbolic_agentkit_core.actions.get_current_balance import GetCurrentBalanceAction
from hyperbolic_agentkit_core.actions.ssh_access import SSHAccessAction


def get_all_hyperbolic_actions() -> list[type[HyperbolicAction]]:
    actions = []
    for action in HyperbolicAction.__subclasses__():
        actions.append(action())
    return actions


HYPERBOLIC_ACTIONS = get_all_hyperbolic_actions()

__all__ = [
    "HYPERBOLIC_ACTIONS",
    "HyperbolicAction",
    "RentComputeAction",
    "GetAvailableGpusAction",
    "GetGpuStatusAction",
    "SSHAccessAction",
    "RemoteShellAction", 
    "TerminateComputeAction", 
    "GetSpendHistoryAction", 
    "GetCurrentBalanceAction",
    "DeployValidatorNodeAction",
]
