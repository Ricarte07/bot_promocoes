package main

import (
	"testing"
	"time"

	"github.com/Ricarte07/bot_promocoes/notifier/internal/infrastructure/telegram"
)

func TestLerIntervalo(t *testing.T) {
	casos := map[string]time.Duration{
		"":      telegram.IntervaloPadrao,
		"90":    90 * time.Second,
		"1.1":   1100 * time.Millisecond,
		"1,5":   1500 * time.Millisecond,
		" 30 ":  30 * time.Second,
		"0.5":   500 * time.Millisecond,
		"120.0": 2 * time.Minute,
	}
	for entrada, esperado := range casos {
		obtido, err := lerIntervalo(entrada)
		if err != nil {
			t.Errorf("lerIntervalo(%q): erro inesperado %v", entrada, err)
			continue
		}
		if obtido != esperado {
			t.Errorf("lerIntervalo(%q) = %v, esperava %v", entrada, obtido, esperado)
		}
	}
}

func TestLerIntervaloRejeitaValoresInvalidos(t *testing.T) {
	for _, entrada := range []string{"abc", "0", "-5", "1s"} {
		if _, err := lerIntervalo(entrada); err == nil {
			t.Errorf("lerIntervalo(%q): esperava erro", entrada)
		}
	}
}
