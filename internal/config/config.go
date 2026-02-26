package config

import (
	"fmt"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

// Config holds the complete application configuration
type Config struct {
	Server        ServerConfig   `yaml:"server"`
	Sidecars      SidecarConfig  `yaml:"sidecars"`
	ValidUserIDs  []string       `yaml:"valid_user_ids"`
}

// ServerConfig holds HTTP server configuration
type ServerConfig struct {
	Port                int `yaml:"port"`
	ReadTimeoutSeconds  int `yaml:"read_timeout_seconds"`
	WriteTimeoutSeconds int `yaml:"write_timeout_seconds"`
}

// SidecarConfig holds URLs and timeouts for all sidecars
type SidecarConfig struct {
	VoiceURL       string `yaml:"voice_url"`
	LLMURL         string `yaml:"llm_url"`
	LearningURL    string `yaml:"learning_url"`
	TimeoutSeconds int    `yaml:"timeout_seconds"`
}

// GetReadTimeout returns the configured read timeout as time.Duration
func (s *ServerConfig) GetReadTimeout() time.Duration {
	return time.Duration(s.ReadTimeoutSeconds) * time.Second
}

// GetWriteTimeout returns the configured write timeout as time.Duration
func (s *ServerConfig) GetWriteTimeout() time.Duration {
	return time.Duration(s.WriteTimeoutSeconds) * time.Second
}

// GetSidecarTimeout returns the configured sidecar timeout as time.Duration
func (s *SidecarConfig) GetSidecarTimeout() time.Duration {
	return time.Duration(s.TimeoutSeconds) * time.Second
}

// Load reads and parses the configuration file
func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config file: %w", err)
	}

	// Validate configuration
	if err := cfg.Validate(); err != nil {
		return nil, fmt.Errorf("invalid configuration: %w", err)
	}

	return &cfg, nil
}

// Validate ensures all required configuration fields are set
func (c *Config) Validate() error {
	if c.Server.Port <= 0 || c.Server.Port > 65535 {
		return fmt.Errorf("invalid server port: %d", c.Server.Port)
	}

	if c.Sidecars.VoiceURL == "" {
		return fmt.Errorf("voice_url is required")
	}

	if c.Sidecars.LLMURL == "" {
		return fmt.Errorf("llm_url is required")
	}

	if c.Sidecars.LearningURL == "" {
		return fmt.Errorf("learning_url is required")
	}

	if len(c.ValidUserIDs) == 0 {
		return fmt.Errorf("at least one valid_user_id is required")
	}

	return nil
}

// IsValidUserID checks if a user ID is in the list of valid user IDs
func (c *Config) IsValidUserID(userID string) bool {
	for _, id := range c.ValidUserIDs {
		if id == userID {
			return true
		}
	}
	return false
}
