"""Shared Laya runtime: loads checkpoints and answers typed questions.

Used by server.py (HTTP API) and mcp_server.py (MCP bridge).

Laya is a non-autoregressive System-1 decision model: you give it a `state`
(text / email / ticket / JSON) plus typed `questions` (choice / noul / score),
and it returns calibrated answers in a single forward pass (~35 ms).
It never generates text.
"""
import os
import threading
import time
import unicodedata

# README note: transformers probes TensorFlow at import; if TF is installed its
# abseil runtime can deadlock model construction. Disable it.
os.environ.setdefault("USE_TF", "0")

DEFAULT_MODEL_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "models", "laya"
)

# canonical checkpoint name -> (subfolder inside the repo, weight file to check)
CHECKPOINTS = {
    "english": (None, "model.safetensors"),
    "multilingual": ("multilingual", os.path.join("multilingual", "model.safetensors")),
    "typed-decisions": (
        "typed-decisions",
        os.path.join("typed-decisions", "model.safetensors"),
    ),
}

# names external clients may send -> canonical checkpoint.
# "jev*" aliases make this server a drop-in for TypeSafe SDK tooling.
ALIASES = {
    "jev": "english",
    "jev-latest": "english",
    "jev-1.13.0": "english",
    "jev-1.13": "english",
    "laya": "english",
    "laya-english": "english",
    "english": "english",
    "en": "english",
    "multilingual": "multilingual",
    "laya-multilingual": "multilingual",
    "typed-decisions": "typed-decisions",
    "laya-typed-decisions": "typed-decisions",
    "td": "typed-decisions",
}


def canonical_model(name):
    return ALIASES.get(str(name).strip().lower(), str(name).strip().lower())


class LayaRuntime:
    """Lazy, thread-safe loader + predictor for the local Laya checkpoints."""

    def __init__(self, model_dir=DEFAULT_MODEL_DIR, device="auto"):
        self.model_dir = os.path.abspath(model_dir)
        self.device = self._resolve_device(device)
        self._agents = {}
        self._load_lock = threading.Lock()
        self._predict_lock = threading.Lock()

    @staticmethod
    def _resolve_device(device):
        if device and device != "auto":
            return device
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def available(self):
        """Which checkpoints have weights on disk."""
        return [
            name
            for name, (_, weight) in CHECKPOINTS.items()
            if os.path.exists(os.path.join(self.model_dir, weight))
        ]

    def load(self, name):
        name = canonical_model(name)
        if name not in CHECKPOINTS:
            raise KeyError(
                "unknown model %r; available: %s"
                % (name, self.available() or "<nothing downloaded yet>")
            )
        with self._load_lock:
            if name in self._agents:
                return self._agents[name]
            subfolder, weight = CHECKPOINTS[name]
            if not os.path.exists(os.path.join(self.model_dir, weight)):
                raise FileNotFoundError(
                    "weights for %r not found at %s. Run:  start.bat  (or "
                    "download_model.py --variant %s)"
                    % (name, os.path.join(self.model_dir, weight), name)
                )
            import laya

            agent = laya.load(self.model_dir, device=self.device, subfolder=subfolder)
            self._agents[name] = agent
            return agent

    @staticmethod
    def state_text(state):
        """Best-effort flattening of a state into plain text (for routing)."""
        if isinstance(state, str):
            return state
        if isinstance(state, dict):
            return " ".join(
                str(v) for v in state.values() if isinstance(v, (str, int, float))
            )
        if isinstance(state, list):
            return " ".join(str(v) for v in state)
        return str(state)

    @staticmethod
    def looks_non_latin(text):
        """True when the text is mostly written in a non-Latin script."""
        letters = 0
        non_latin = 0
        for ch in text:
            if not ch.isalpha():
                continue
            letters += 1
            try:
                name = unicodedata.name(ch)
            except ValueError:
                continue
            if not name.startswith("LATIN"):
                non_latin += 1
        return letters >= 8 and (non_latin / letters) > 0.3

    def resolve_name(self, model, state):
        if model:
            return canonical_model(model)
        # auto-route: non-Latin scripts go to the multilingual checkpoint when present
        avail = self.available()
        if "multilingual" in avail and self.looks_non_latin(self.state_text(state)):
            return "multilingual"
        return "english" if "english" in avail else (avail[0] if avail else "english")

    @staticmethod
    def validate_questions(questions):
        if not isinstance(questions, dict) or not questions:
            raise ValueError(
                "'questions' must be a non-empty object, e.g. "
                '{"urgency": {"type": "noul", "instructions": "Is this urgent?"}}'
            )
        for qid, q in questions.items():
            if not isinstance(q, dict) or q.get("type") not in ("choice", "noul", "score"):
                raise ValueError(
                    "question %r must be an object with 'type' in "
                    "(choice, noul, score); got %r" % (qid, q)
                )

    def predict(self, state, questions, model=None):
        """Run one single-forward-pass decision over all questions."""
        self.validate_questions(questions)
        name = self.resolve_name(model, state)
        agent = self.load(name)
        t0 = time.perf_counter()
        with self._predict_lock:
            result = agent.predict(state, questions)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        answers = result.get("answers", {}) if isinstance(result, dict) else {}
        return {
            "model": name,
            "device": self.device,
            "latency_ms": round(latency_ms, 1),
            "answers": answers,
            "routing": {
                "model": name,
                "repo": "convaiinnovations/laya"
                + ("" if name == "english" else "/" + name),
                "requested_model": model,
            },
        }


def to_typesafe_answers(questions, answers):
    """Normalize Laya answers into the TypeSafe /v1/systemone answer shapes.

    choice -> {type, choice, confidence, probabilities}
    noul   -> {type, noul}
    score  -> {type, score, confidence, legend, probabilities}
    """
    out = {}
    for qid, q in questions.items():
        qtype = q.get("type")
        ans = dict(answers.get(qid) or {})
        probs = ans.get("probabilities") or {}
        if qtype == "noul":
            ans.setdefault("type", "noul")
            if "noul" not in ans:
                if "yes" in probs:
                    ans["noul"] = probs["yes"]
                elif "true" in probs:
                    ans["noul"] = probs["true"]
        elif qtype == "choice":
            ans.setdefault("type", "choice")
            if "confidence" not in ans and probs:
                ans["confidence"] = round(max(probs.values()), 4)
        elif qtype == "score":
            ans.setdefault("type", "score")
            if "confidence" not in ans and probs:
                ans["confidence"] = round(max(probs.values()), 4)
            if "legend" not in ans and probs:
                ans["legend"] = probs
        out[qid] = ans
    return out
