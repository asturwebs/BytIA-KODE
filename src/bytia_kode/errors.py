"""Excepciones propias de BytIA-KODE."""


class AgentCancelledError(Exception):
    """El usuario pulsó un Panic Button (interrupt/kill) y el loop lo observó.

    NO hereda de RuntimeError a propósito: chat() captura RuntimeError (junto
    a TimeoutError/ConnectionError/httpx.HTTPError) como fallo de provider con
    failover — una cancelación que heredara de ahí se enredaría en esa red y
    acabaría reportada como caída del provider.

    El cleanup estructurado (persistir el parcial, responder los tool_calls
    pendientes, descolgar widgets de la TUI) vive en el CATCHER, no en el
    raise: chat() la captura en el punto de cancelación y hace el trabajo en
    un solo sitio; las embeddings pueden capturarla si quieren el suyo.

    Atributos:
        partial_text: texto streamado antes de la cancelación (streaming
            parcial; vacío si el corte llegó antes del primer chunk).
        pending_tool_calls: [(tool_call_id, tool_name)] del lote que NO llegó
            a ejecutarse — el catcher debe responderlos explícitamente para
            que la transcripción no quede con tool_calls colgados.
    """

    def __init__(
        self,
        partial_text: str = "",
        pending_tool_calls: list | None = None,
    ):
        super().__init__("agent cancelled by user")
        self.partial_text = partial_text
        self.pending_tool_calls = list(pending_tool_calls or [])
