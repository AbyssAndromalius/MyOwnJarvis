package main

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

// Config represents the application configuration
type Config struct {
	Server struct {
		Host string `yaml:"host"`
		Port int    `yaml:"port"`
	} `yaml:"server"`
	Orchestrator struct {
		URL            string `yaml:"url"`
		TimeoutSeconds int    `yaml:"timeout_seconds"`
	} `yaml:"orchestrator"`
	Session struct {
		MaxHistory int `yaml:"max_history"`
	} `yaml:"session"`
	TTS struct {
		Enabled         bool     `yaml:"enabled"`
		VoicePreference []string `yaml:"voice_preference"`
	} `yaml:"tts"`
}

// LoadConfig reads and parses the config.yaml file
func LoadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config file: %w", err)
	}

	// Set defaults if not specified
	if cfg.Server.Host == "" {
		cfg.Server.Host = "127.0.0.1"
	}
	if cfg.Server.Port == 0 {
		cfg.Server.Port = 10090
	}
	if cfg.Orchestrator.URL == "" {
		cfg.Orchestrator.URL = "http://localhost:10080"
	}
	if cfg.Orchestrator.TimeoutSeconds == 0 {
		cfg.Orchestrator.TimeoutSeconds = 60
	}
	if cfg.Session.MaxHistory == 0 {
		cfg.Session.MaxHistory = 20
	}

	return &cfg, nil
}
