"""Configuration management for MTG Deck Builder."""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class DeckBuildingConfig:
    """Configuration settings for deck building."""
    
    # Deck composition preferences
    min_lands: int = 35
    max_lands: int = 40
    preferred_creature_count: int = 25
    preferred_noncreature_spells: int = 35
    
    # Algorithm weights
    synergy_weight: float = 0.7
    availability_weight: float = 0.3
    
    # API settings
    edhrec_cache_enabled: bool = True
    edhrec_cache_duration_hours: int = 24
    api_retry_attempts: int = 3
    api_timeout_seconds: int = 30
    
    # Output preferences
    default_output_dir: str = "."
    include_statistics: bool = True
    verbose_output: bool = False
    
    # Deck validation
    min_deck_size: int = 100
    enforce_singleton: bool = True
    enforce_color_identity: bool = True
    
    # File handling
    csv_encoding: str = "utf-8"
    backup_files: bool = False


class ConfigManager:
    """Manages application configuration with file persistence."""
    
    DEFAULT_CONFIG_DIR = Path.home() / ".mtg_deck_builder"
    DEFAULT_CONFIG_FILE = "config.json"
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Custom configuration directory (defaults to ~/.mtg_deck_builder)
        """
        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self.config_file = self.config_dir / self.DEFAULT_CONFIG_FILE
        self._config = DeckBuildingConfig()
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing config if available
        self.load_config()
    
    def load_config(self) -> DeckBuildingConfig:
        """
        Load configuration from file.
        
        Returns:
            Loaded configuration object
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # Update config with loaded values
                for key, value in config_data.items():
                    if hasattr(self._config, key):
                        setattr(self._config, key, value)
                
            except (json.JSONDecodeError, OSError) as e:
                # If config file is corrupted, use defaults and create backup
                if self.config_file.exists():
                    backup_file = self.config_file.with_suffix('.json.backup')
                    self.config_file.rename(backup_file)
                
                # Save default config
                self.save_config()
        else:
            # Create default config file
            self.save_config()
        
        return self._config
    
    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            config_data = asdict(self._config)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, sort_keys=True)
                
        except OSError as e:
            raise RuntimeError(f"Failed to save configuration: {e}")
    
    def get_config(self) -> DeckBuildingConfig:
        """Get current configuration."""
        return self._config
    
    def update_config(self, **kwargs) -> None:
        """
        Update configuration values.
        
        Args:
            **kwargs: Configuration values to update
        """
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
            else:
                raise ValueError(f"Unknown configuration option: {key}")
        
        self.save_config()
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self._config = DeckBuildingConfig()
        self.save_config()
    
    def get_cache_dir(self) -> Path:
        """Get cache directory path."""
        cache_dir = self.config_dir / "cache"
        cache_dir.mkdir(exist_ok=True)
        return cache_dir
    
    def get_logs_dir(self) -> Path:
        """Get logs directory path."""
        logs_dir = self.config_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        return logs_dir
    
    @classmethod
    def create_sample_config(cls, output_path: Path) -> None:
        """
        Create a sample configuration file with comments.
        
        Args:
            output_path: Path where to create the sample config
        """
        sample_config = {
            "// Deck composition preferences": None,
            "min_lands": 35,
            "max_lands": 40,
            "preferred_creature_count": 25,
            "preferred_noncreature_spells": 35,
            
            "// Algorithm weights (0.0 to 1.0)": None,
            "synergy_weight": 0.7,
            "availability_weight": 0.3,
            
            "// API settings": None,
            "edhrec_cache_enabled": True,
            "edhrec_cache_duration_hours": 24,
            "api_retry_attempts": 3,
            "api_timeout_seconds": 30,
            
            "// Output preferences": None,
            "default_output_dir": ".",
            "include_statistics": True,
            "verbose_output": False,
            
            "// Deck validation": None,
            "min_deck_size": 60,
            "enforce_singleton": True,
            "enforce_color_identity": True,
            
            "// File handling": None,
            "csv_encoding": "utf-8",
            "backup_files": False
        }
        
        # Remove comment keys for actual JSON
        clean_config = {k: v for k, v in sample_config.items() if not k.startswith("//")}
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("// MTG Deck Builder Configuration\n")
            f.write("// Remove this comment line to use as actual config.json\n")
            f.write("{\n")
            
            for key, value in sample_config.items():
                if key.startswith("//"):
                    f.write(f'  "{key}",\n')
                else:
                    f.write(f'  "{key}": {json.dumps(value)},\n')
            
            f.write("}\n")


def get_default_config() -> DeckBuildingConfig:
    """Get default configuration without file persistence."""
    return DeckBuildingConfig()


def load_user_config() -> DeckBuildingConfig:
    """Load user configuration from default location."""
    manager = ConfigManager()
    return manager.get_config()


# Environment variable overrides
def apply_env_overrides(config: DeckBuildingConfig) -> DeckBuildingConfig:
    """
    Apply environment variable overrides to configuration.
    
    Args:
        config: Base configuration to override
        
    Returns:
        Configuration with environment overrides applied
    """
    env_mappings = {
        'MTG_DECK_BUILDER_MIN_LANDS': ('min_lands', int),
        'MTG_DECK_BUILDER_MAX_LANDS': ('max_lands', int),
        'MTG_DECK_BUILDER_SYNERGY_WEIGHT': ('synergy_weight', float),
        'MTG_DECK_BUILDER_CACHE_ENABLED': ('edhrec_cache_enabled', lambda x: x.lower() == 'true'),
        'MTG_DECK_BUILDER_OUTPUT_DIR': ('default_output_dir', str),
        'MTG_DECK_BUILDER_VERBOSE': ('verbose_output', lambda x: x.lower() == 'true'),
        'MTG_DECK_BUILDER_MIN_DECK_SIZE': ('min_deck_size', int),
    }
    
    for env_var, (attr_name, converter) in env_mappings.items():
        env_value = os.getenv(env_var)
        if env_value is not None:
            try:
                converted_value = converter(env_value)
                setattr(config, attr_name, converted_value)
            except (ValueError, TypeError):
                # Ignore invalid environment values
                pass
    
    return config