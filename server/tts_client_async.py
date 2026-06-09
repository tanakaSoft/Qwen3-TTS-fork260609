# coding=utf-8
# Fork addition (not part of upstream Qwen3-TTS).
#
# Thin HTTP client for the async TTS server (server/tts_server_async.py).
# Usable from Windows or from other apps inside WSL2 — it only needs
# `requests`, `numpy` and `soundfile` (no torch / GPU).
#
# SPDX-License-Identifier: Apache-2.0
import base64
import time
from typing import List, Optional, Tuple

import numpy as np
import requests
import soundfile as sf


class QwenTTSAsyncClient:
    """Client for the fork's Qwen3-TTS async API server."""

    def __init__(self, server_url: str = "http://localhost:8001", timeout: float = 600.0):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self._check_connection()

    # ------------------------------------------------------------------ #
    # Connection / metadata
    # ------------------------------------------------------------------ #
    def _check_connection(self) -> None:
        try:
            resp = requests.get(f"{self.server_url}/health", timeout=5)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise ConnectionError(f"Cannot reach TTS server at {self.server_url}: {exc}")
        print(f"[OK] Connected to TTS server: {self.server_url}")

    def health(self) -> dict:
        return requests.get(f"{self.server_url}/health", timeout=5).json()

    def supported_speakers(self) -> Optional[List[str]]:
        return requests.get(f"{self.server_url}/supported_speakers", timeout=10).json()["speakers"]

    def supported_languages(self) -> Optional[List[str]]:
        return requests.get(f"{self.server_url}/supported_languages", timeout=10).json()["languages"]

    def gpu_stats(self) -> dict:
        return requests.get(f"{self.server_url}/gpu_stats", timeout=10).json()

    def clear_gpu_cache(self) -> dict:
        return requests.post(f"{self.server_url}/clear_gpu_cache", timeout=10).json()

    def whisper_models(self) -> dict:
        return requests.get(f"{self.server_url}/whisper_models", timeout=10).json()

    # ------------------------------------------------------------------ #
    # Generation
    # ------------------------------------------------------------------ #
    def generate_custom_voice(
        self, text: str, speaker: str = "speaker_custom",
        instruct: str = "", language: str = "Japanese",
    ) -> Tuple[np.ndarray, int]:
        resp = requests.post(
            f"{self.server_url}/generate_custom_voice",
            json={"text": text, "speaker": speaker, "instruct": instruct, "language": language},
            timeout=self.timeout,
        )
        return self._unpack_audio(resp)

    def batch_generate_custom_voice(
        self, texts: List[str], speaker: str = "speaker_custom",
        instruct: str = "", language: str = "Japanese",
    ) -> Tuple[List[np.ndarray], int]:
        resp = requests.post(
            f"{self.server_url}/batch_generate_custom_voice",
            json={"texts": texts, "speaker": speaker, "instruct": instruct, "language": language},
            timeout=self.timeout,
        )
        self._raise_for_status(resp)
        data = resp.json()
        audios = [self._decode_audio(a) for a in data["audios"]]
        return audios, data["sample_rate"]

    def generate_voice_design(
        self, text: str, instruct: str, language: str = "Japanese",
    ) -> Tuple[np.ndarray, int]:
        resp = requests.post(
            f"{self.server_url}/generate_voice_design",
            json={"text": text, "instruct": instruct, "language": language},
            timeout=self.timeout,
        )
        return self._unpack_audio(resp)

    def generate_voice_clone(
        self, text: str, ref_audio_path: str, ref_text: str,
        language: str = "Auto", x_vector_only_mode: bool = False,
    ) -> Tuple[np.ndarray, int]:
        with open(ref_audio_path, "rb") as f:
            resp = requests.post(
                f"{self.server_url}/generate_voice_clone",
                data={
                    "text": text,
                    "ref_text": ref_text,
                    "language": language,
                    "x_vector_only_mode": str(x_vector_only_mode).lower(),
                },
                files={"ref_audio": f},
                timeout=self.timeout,
            )
        return self._unpack_audio(resp)

    # ------------------------------------------------------------------ #
    # Whisper auto-transcription
    # ------------------------------------------------------------------ #
    def auto_transcribe(
        self, audio_path: str, model: str = "", language: str = "",
    ) -> str:
        """Transcribe an audio file via the server's Whisper model. Returns text."""
        with open(audio_path, "rb") as f:
            resp = requests.post(
                f"{self.server_url}/auto_transcribe",
                data={"model": model, "language": language},
                files={"audio": f},
                timeout=self.timeout,
            )
        self._raise_for_status(resp)
        return resp.json()["text"]

    # ------------------------------------------------------------------ #
    # Fine-tuning
    # ------------------------------------------------------------------ #
    def start_finetune(
        self, train_jsonl: str, output_model_name: str = "finetuned_model",
        num_epochs: int = 10, batch_size: int = 32, lr: float = 2e-6,
        speaker_name: str = "speaker_custom",
    ) -> str:
        resp = requests.post(
            f"{self.server_url}/finetune_async",
            json={
                "train_jsonl": train_jsonl,
                "output_model_name": output_model_name,
                "num_epochs": num_epochs,
                "batch_size": batch_size,
                "lr": lr,
                "speaker_name": speaker_name,
            },
            timeout=30,
        )
        self._raise_for_status(resp)
        return resp.json()["job_id"]

    def get_finetune_status(self, job_id: str) -> dict:
        resp = requests.get(f"{self.server_url}/finetune_status/{job_id}", timeout=10)
        self._raise_for_status(resp)
        return resp.json()

    def list_finetune_jobs(self) -> dict:
        resp = requests.get(f"{self.server_url}/finetune_jobs", timeout=10)
        self._raise_for_status(resp)
        return resp.json()

    def wait_finetune_completion(
        self, job_id: str, check_interval: float = 10.0, verbose: bool = True,
    ) -> dict:
        while True:
            status = self.get_finetune_status(job_id)
            if verbose:
                print(f"  {status['progress']:3d}% - {status['message']}")
            if status["status"] == "completed":
                return status
            if status["status"] == "failed":
                raise RuntimeError(status["message"])
            time.sleep(check_interval)

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #
    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        if resp.status_code != 200:
            raise RuntimeError(f"API error {resp.status_code}: {resp.text}")

    @staticmethod
    def _decode_audio(audio_base64: str) -> np.ndarray:
        audio_bytes = base64.b64decode(audio_base64)
        return np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32767

    def _unpack_audio(self, resp: requests.Response) -> Tuple[np.ndarray, int]:
        self._raise_for_status(resp)
        data = resp.json()
        return self._decode_audio(data["audio_base64"]), data["sample_rate"]

    @staticmethod
    def save_speech(audio: np.ndarray, sample_rate: int, output_file: str) -> None:
        sf.write(output_file, audio, sample_rate)
        print(f"[saved] {output_file}")


if __name__ == "__main__":
    # Minimal smoke test against a running server.
    tts = QwenTTSAsyncClient()
    print("health:", tts.health())

    audio, sr = tts.generate_voice_design(
        text="これはボイスデザインのテストです。",
        instruct="明るく元気な若い女性の声で、はっきりと話す",
    )
    tts.save_speech(audio, sr, "design_test.wav")
