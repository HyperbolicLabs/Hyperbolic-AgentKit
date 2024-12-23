from hyperbolic_agentkit_core.actions.get_available_gpus import GetAvailableGpusAction
from hyperbolic_agentkit_core.actions.get_gpu_status import GetGpuStatusAction
from hyperbolic_agentkit_core.actions.hyperbolic_action import HyperbolicAction
from hyperbolic_agentkit_core.actions.remote_shell import RemoteShellAction
from hyperbolic_agentkit_core.actions.rent_compute import RentComputeAction
from hyperbolic_agentkit_core.actions.ssh_access import SSHAccessAction
from hyperbolic_agentkit_core.actions.setup_ethereum_validator import SetupValidatorAction
from hyperbolic_agentkit_core.actions.terminate_instance import TerminateInstanceAction


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
    "SetupValidatorAction",
    "TerminateInstanceAction",
]
