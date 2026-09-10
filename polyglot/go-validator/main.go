package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"
)

type Candle struct { Time int64; Open, High, Low, Close float64; Volume *float64 }

func parse(row string) (Candle, error) {
	parts := strings.Split(strings.TrimSpace(row), "\t")
	if len(parts) < 5 || len(parts) > 6 { return Candle{}, fmt.Errorf("expected 5 or 6 tab-separated fields") }
	t, err := strconv.ParseInt(parts[0], 10, 64); if err != nil || t <= 0 { return Candle{}, fmt.Errorf("invalid time") }
	vals := make([]float64, 4)
	for i := range vals { v, e := strconv.ParseFloat(parts[i+1], 64); if e != nil || math.IsNaN(v) || math.IsInf(v, 0) || v <= 0 { return Candle{}, fmt.Errorf("invalid price") }; vals[i] = v }
	open, high, low, close := vals[0], vals[1], vals[2], vals[3]
	if high < open || high < close || low > open || low > close || low > high { return Candle{}, fmt.Errorf("invalid candle geometry") }
	c := Candle{Time:t, Open:open, High:high, Low:low, Close:close}
	if len(parts) == 6 { v, e := strconv.ParseFloat(parts[5], 64); if e != nil || math.IsNaN(v) || math.IsInf(v, 0) || v < 0 { return Candle{}, fmt.Errorf("invalid volume") }; c.Volume = &v }
	return c, nil
}

func main() {
	enc := json.NewEncoder(os.Stdout); s := bufio.NewScanner(os.Stdin); var previous int64
	for index := 0; s.Scan(); index++ {
		line := s.Text(); if strings.TrimSpace(line) == "" { continue }
		c, err := parse(line)
		if err == nil && c.Time <= previous { err = fmt.Errorf("timestamp must be strictly increasing") }
		if err != nil { _ = enc.Encode(map[string]any{"ok":false,"index":index,"error":err.Error()}); continue }
		previous = c.Time
		_ = enc.Encode(map[string]any{"ok":true,"index":index,"time":c.Time,"open":c.Open,"high":c.High,"low":c.Low,"close":c.Close,"volume":c.Volume})
	}
	if err := s.Err(); err != nil { fmt.Fprintln(os.Stderr, err) }
}
