public final class MarketDataValidator {
    private MarketDataValidator() {}

    private static String json(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private static String validate(String line, int index, long previous) {
        String[] p = line.trim().split("\\t", -1);
        if (p.length < 5 || p.length > 6) return "{\"ok\":false,\"index\":" + index + ",\"error\":\"expected 5 or 6 tab-separated fields\"}";
        try {
            long time = Long.parseLong(p[0]);
            double open = Double.parseDouble(p[1]);
            double high = Double.parseDouble(p[2]);
            double low = Double.parseDouble(p[3]);
            double close = Double.parseDouble(p[4]);
            if (time <= previous || time <= 0) return "{\"ok\":false,\"index\":" + index + ",\"error\":\"timestamp must be strictly increasing\"}";
            if (!(Double.isFinite(open) && Double.isFinite(high) && Double.isFinite(low) && Double.isFinite(close)) || open <= 0 || high <= 0 || low <= 0 || close <= 0) {
                return "{\"ok\":false,\"index\":" + index + ",\"error\":\"prices must be finite and positive\"}";
            }
            if (high < open || high < close || low > open || low > close || low > high) return "{\"ok\":false,\"index\":" + index + ",\"error\":\"invalid candle geometry\"}";
            if (p.length == 6) {
                double volume = Double.parseDouble(p[5]);
                if (!Double.isFinite(volume) || volume < 0) return "{\"ok\":false,\"index\":" + index + ",\"error\":\"invalid volume\"}";
                return "{\"ok\":true,\"index\":" + index + ",\"time\":" + time + ",\"open\":" + open + ",\"high\":" + high + ",\"low\":" + low + ",\"close\":" + close + ",\"volume\":" + volume + "}";
            }
            return "{\"ok\":true,\"index\":" + index + ",\"time\":" + time + ",\"open\":" + open + ",\"high\":" + high + ",\"low\":" + low + ",\"close\":" + close + "}";
        } catch (NumberFormatException ex) {
            return "{\"ok\":false,\"index\":" + index + ",\"error\":\"invalid numeric field\"}";
        }
    }

    public static void main(String[] args) throws Exception {
        try (var reader = new java.io.BufferedReader(new java.io.InputStreamReader(System.in))) {
            String line; int index = 0; long previous = 0;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) { index++; continue; }
                String result = validate(line, index, previous);
                System.out.println(result);
                if (result.contains("\"ok\":true")) previous = Long.parseLong(line.trim().split("\\t", -1)[0]);
                index++;
            }
        }
    }
}
