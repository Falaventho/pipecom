# An os-agnostic handler for ipc via named pipes.

from .pipecom import Pipe, send
from ._exceptions import PipeError

__all__ = ['Pipe', 'send', 'PipeError']
