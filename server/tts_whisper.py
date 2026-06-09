# coding=utf-8
# Fork addition (not part of upstream Qwen3-TTS).
#
# Whisper auto-transcription for the VoiceClone workflow.
#
# Uses the *transformers* Whisper implementation, which rides on the same
# torch/CUDA stack already installed for Qwen3-TTS. This deliberately avoids
# faster-whisper / CTranslate2, which on Windows needs separate cuDNN/CUDA DLLs
# (the same class of non-official native-dependency risk we removed with
# Flash Attention 2). Zero extra pip/native dependencies are required here.
#
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import gc
from typing import Optional

import torch

# Friendly model name -> HuggingFace model id. Larger = more accurate, more VRAM.
# RTX 5090 (32 GB) comfortably runs large-v3 alongside the TTS models.
WHISPER_MODEL_MAP = {
    "tiny": "openai/whisper-tiny",
    "base": "openai/whisper-base",
    "small": "openai/whisper-small",
    "medium": "openai/whisper-medium",
    "large-v3": "openai/whisper-large-v3",
}

# Map common UI language names to Whisper language codes. Whisper auto-detects
# when the language is omitted, so this only needs the languages we surface.
_LANGUAGE_ALIASES = {
    "japanese": "japanese", "ja": "japanese", "日本語": "japanese",
    "english": "english", "en": "english",
    "chinese": "chinese", "zh": "chinese", "中文": "chinese",
    "korean": "korean", "ko": "korean",
    "auto": None, "": None,
}


def _resolve_language(language: Optional[str]) -> Optional[str]:
    if language is None:
        return None
    return _LANGUAGE_ALIASES.get(language.strip().lower(), language.strip().lower())


class WhisperTranscriber:
    """Lazy transformers-based Whisper ASR pipeline, bound to one device/dtype."""

    def __init__(self, model_name: str, device: str = "cuda:0", dtype=torch.bfloat16):
        if model_name not in WHISPER_MODEL_MAP:
            raise ValueError(
                f"Unknown Whisper model '{model_name}'. "
                f"Choose from: {', '.join(WHISPER_MODEL_MAP)}"
            )
        self.model_name = model_name
        self._hf_id = WHISPER_MODEL_MAP[model_name]
        self._device = device
        self._dtype = dtype
        self._pipe = self._build_pipeline()

    def _build_pipeline(self):
        from transformers import pipeline

        return pipeline(
            task="automatic-speech-recognition",
            model=self._hf_id,
            torch_dtype=self._dtype,
            device=self._device,
            # chunk_length_s enables long-form transcription (refs > 30 s).
            chunk_length_s=30,
        )

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> str:
        """Transcribe an audio file to plain text.

        Audio is decoded with librosa (already a core dependency) to 16 kHz mono
        and passed to the pipeline as a raw array. This avoids the transformers
        ASR pipeline's default ffmpeg path-decoding, so no ffmpeg binary is
        required on Windows.
        """
        import librosa

        waveform, _ = librosa.load(audio_path, sr=16000, mono=True)

        # transformers 4.57 iterates generate_kwargs, so passing None (when no
        # language is forced / auto-detect) raises TypeError — omit it instead.
        extra = {}
        lang = _resolve_language(language)
        if lang is not None:
            extra["generate_kwargs"] = {"language": lang}
        result = self._pipe(
            {"raw": waveform, "sampling_rate": 16000},
            return_timestamps=False,
            **extra,
        )
        return (result.get("text") or "").strip()

    def unload(self) -> None:
        """Release the model and free VRAM (used when switching models)."""
        self._pipe = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
