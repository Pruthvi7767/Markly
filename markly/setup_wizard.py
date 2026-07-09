"""Textual-based setup wizard for Markly.

Collects API keys, tests connections, and saves them securely via pyrage.
"""
import os
import tomllib
import toml
from pathlib import Path
from openai import OpenAI
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Input, Button, Label, RadioSet, RadioButton, Static
from textual.containers import Vertical, Horizontal, Container

from markly.secrets_manager import save_secrets

def _test_openai_connection(base_url: str, api_key: str) -> bool:
    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        # 1-token cheap completion test or models list
        client.models.list()
        return True
    except Exception:
        return False

class ConnectionTestScreen(Screen):
    """Shows connection testing progress and results."""
    
    def __init__(self, nvidia_key: str, groq_key: str, profile: str):
        super().__init__()
        self.nvidia_key = nvidia_key
        self.groq_key = groq_key
        self.profile = profile
        self.nvidia_ok = False
        self.groq_ok = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="test-container", classes="p-4"):
            yield Label("Testing connections...", id="status-label")
            yield Label("", id="nvidia-status")
            yield Label("", id="groq-status")
            yield Button("Finish & Save", id="btn-finish", variant="success", disabled=True)
            yield Button("Back", id="btn-back", variant="warning")
        yield Footer()
        
    def on_mount(self):
        self.run_worker(self.test_connections(), exclusive=True)
        
    async def test_connections(self):
        status_label = self.query_one("#status-label", Label)
        btn_finish = self.query_one("#btn-finish", Button)
        
        nvidia_status = self.query_one("#nvidia-status", Label)
        groq_status = self.query_one("#groq-status", Label)
        
        if self.nvidia_key:
            nvidia_status.update("NVIDIA NIM: Testing...")
            ok = _test_openai_connection("https://integrate.api.nvidia.com/v1", self.nvidia_key)
            self.nvidia_ok = ok
            if ok:
                nvidia_status.update("NVIDIA NIM: ✅ Connected")
            else:
                nvidia_status.update("NVIDIA NIM: ❌ Failed (check key)")
        else:
            self.nvidia_ok = False
            nvidia_status.update("NVIDIA NIM: No key provided")
            
        if self.groq_key:
            groq_status.update("Groq: Testing...")
            ok = _test_openai_connection("https://api.groq.com/openai/v1", self.groq_key)
            self.groq_ok = ok
            if ok:
                groq_status.update("Groq: ✅ Connected")
            else:
                groq_status.update("Groq: ❌ Failed (check key)")
        else:
            self.groq_ok = True  # Optional, so OK if missing
            groq_status.update("Groq: Not configured")
            
        status_label.update("Testing complete.")
        
        if self.nvidia_ok:
            btn_finish.disabled = False
            
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-finish":
            secrets = {}
            if self.nvidia_key:
                secrets["NVIDIA_API_KEY"] = self.nvidia_key
            if self.groq_key:
                secrets["GROQ_API_KEY"] = self.groq_key
            
            save_secrets(secrets)
            
            # Save profile to config.toml
            cfg_path = Path(__file__).parent.parent / "config.toml"
            if cfg_path.exists():
                with open(cfg_path, "rb") as f:
                    cfg = tomllib.load(f)
            else:
                cfg = {}
                
            cfg["infra_profile"] = self.profile
            # Provide default models if none exist
            if "models" not in cfg:
                cfg["models"] = {
                    "planner": "mistralai/mistral-large-3-675b-instruct-2512",
                    "verifier": "mistralai/mistral-large-3-675b-instruct-2512",
                    "critic": "microsoft/phi-4-mini-instruct",
                    "base_url": "https://integrate.api.nvidia.com/v1"
                }
                
            with open(cfg_path, "w", encoding="utf-8") as f:
                toml.dump(cfg, f)
                
            self.app.exit(result=True)
            
        elif event.button.id == "btn-back":
            self.app.pop_screen()


class SetupWizardScreen(Screen):
    """Main setup screen for Markly."""
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="setup-form", classes="p-4"):
            yield Label("Welcome to Markly Setup", classes="text-bold text-xl mb-2")
            
            yield Label("NVIDIA NIM API Key (Required for Primary Models):")
            yield Input(placeholder="nvapi-...", password=True, id="nvidia-key")
            
            yield Label("Groq API Key (Optional, for fallback):", classes="mt-2")
            yield Input(placeholder="gsk_...", password=True, id="groq-key")
            
            yield Label("Infrastructure Profile:", classes="mt-2")
            with RadioSet(id="infra-profile"):
                yield RadioButton("Lightweight (Default, fast, local state)", value=True, id="prof-light")
                yield RadioButton("Heavy (Requires Docker, local Chroma, Postgres)", id="prof-heavy")
                
            yield Button("Test Connections & Save", variant="primary", id="btn-next", classes="mt-4")
            
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-next":
            nvidia_key = self.query_one("#nvidia-key", Input).value
            groq_key = self.query_one("#groq-key", Input).value
            
            if not nvidia_key:
                self.notify("NVIDIA API Key is required.", severity="error")
                return
                
            radios = self.query_one(RadioSet)
            profile = "lightweight" if radios.pressed_button and radios.pressed_button.id == "prof-light" else "heavy"
            
            self.app.push_screen(ConnectionTestScreen(nvidia_key, groq_key, profile))


class SetupWizardApp(App):
    """The Markly Setup Wizard application."""
    
    CSS = """
    #setup-form, #test-container {
        padding: 1 2;
        width: 100%;
        max-width: 80;
        align-horizontal: center;
        margin: 1 2;
    }
    .text-bold {
        text-style: bold;
    }
    .text-xl {
        text-style: bold;
    }
    .mb-2 {
        margin-bottom: 1;
    }
    .mt-2 {
        margin-top: 1;
    }
    .mt-4 {
        margin-top: 2;
    }
    """
    
    def on_mount(self) -> None:
        self.push_screen(SetupWizardScreen())


def run_setup_wizard():
    app = SetupWizardApp()
    result = app.run()
    return result
