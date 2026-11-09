"""Transport-neutral application entrypoint for future HTTP and worker layers."""
from pandoria.contracts import CognitiveRequest, CognitiveResponse
from pandoria.kernel import CognitiveKernel

class PandoriaApplication:
    def __init__(self, kernel: CognitiveKernel | None = None) -> None:
        self.kernel = kernel or CognitiveKernel()
    async def handle(self, text: str, *, user_id: str | None = None,
                     session_id: str | None = None) -> CognitiveResponse:
        return await self.kernel.process(CognitiveRequest(
            text=text, user_id=user_id, session_id=session_id))
