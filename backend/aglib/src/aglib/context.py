
from typing import List, Dict, Any, Optional
from .client import Response
from .tools import ToolOutput


# === CONTEXT ===


class Context:
    """Container for full history and a per-turn frame used to build LLM messages."""

    def __init__(self):
        self.history: List[Dict[str, Any]] = []  # entire conversation log
        self.frame: List[Dict[str, Any]] = []    # transient per-agent view
        self._system_override: Optional[str] = None  # temporary replacement for base system prompt

    def get_view(self) -> List[Dict[str, Any]]:
        # maintain compatibility: view == current frame
        return list(self.frame)

    def build_messages(self, base_system_prompt: Optional[str] = None) -> List[Dict[str, Any]]:
        """Build messages for the LLM: [system] + frame.

        - Uses override system prompt if set; otherwise uses provided base.
        - Frame should contain only the messages relevant for the current agent turn
          (e.g., user query, instructions/objectives, selected tool/agent outputs).
        """
        messages: List[Dict[str, Any]] = []

        system_content = self._system_override if self._system_override is not None else base_system_prompt
        if system_content:
            messages.append({"role": "system", "content": system_content})

        messages.extend(self.get_view())
        return messages

    def clear(self):
        # clear per-turn frame and system override; keep full history
        self.frame = []
        self._system_override = None

    def add_user_query(self, text: str, *, to_frame: bool = True):
        msg = {"role": "user", "content": text}
        if to_frame:
            self.frame.append(msg)
        self.history.append(msg)

    def add_instruction(self, instruction: str, *, to_frame: bool = True):
        """Add an instruction as a system message; recorded in history and optionally in the frame."""
        msg = {"role": "system", "content": instruction}
        if to_frame:
            self.frame.append(msg)
        self.history.append(msg)

    def override_system_prompt(self, prompt: Optional[str]):
        """Temporarily replace the base system prompt for this turn's messages."""
        self._system_override = prompt

    def add_model_response(self, response: Response, *, to_frame: bool = True):
        msg = {"role": "assistant", "content": response.content}
        if to_frame:
            self.frame.append(msg)
        self.history.append(msg)

    def add_error(self, error: Exception, iter_index: int, *, to_frame: bool = True):
        msg = {"role": "system", "content": f"error at iter {iter_index}: {error}"}
        if to_frame:
            self.frame.append(msg)
        self.history.append(msg)

    def add_tool_outputs(self, outputs: List[ToolOutput], *, mode: str = "content", header: Optional[str] = None, to_frame: bool = True,):
        """Bring previous tool outputs into the current frame.

        - mode='content' (default): adds a single system message summarizing content/errors.
        - mode='full': add full tool output
        """
        if mode == "full":
            for o in outputs:
                content = o.content if o.error is None else f"ERROR: {o.error}"
                msg = {"role": "tool", "name": o.tool_name, "content": content, "call_id": o.call_id}
                if to_frame:
                    self.frame.append(msg)
                self.history.append(msg)
        elif mode == "content":
            header_text = header or "Context from previous tools:"
            lines: List[str] = [header_text]
            for o in outputs:
                if o.error:
                    lines.append(f"- {o.tool_name} ERROR: {o.error}")
                else:
                    lines.append(f"- {o.tool_name}: {o.content}")
            content = "\n".join(lines)
            msg = {"role": "system", "content": content}
            if to_frame:
                self.frame.append(msg)
            self.history.append(msg)


