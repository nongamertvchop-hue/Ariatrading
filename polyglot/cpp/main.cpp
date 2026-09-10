#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

struct Candle { long long time; double open, high, low, close; double volume; bool has_volume; };

static bool parse(const std::string& line, Candle& c, std::string& error) {
    std::stringstream ss(line);
    std::string field;
    std::vector<std::string> p;
    while (std::getline(ss, field, '\t')) p.push_back(field);
    if (p.size() < 5 || p.size() > 6) { error = "expected 5 or 6 tab-separated fields"; return false; }
    try {
        c.time = std::stoll(p[0]);
        c.open = std::stod(p[1]); c.high = std::stod(p[2]); c.low = std::stod(p[3]); c.close = std::stod(p[4]);
        c.has_volume = p.size() == 6;
        if (c.has_volume) c.volume = std::stod(p[5]);
    } catch (...) { error = "invalid numeric field"; return false; }
    if (c.time <= 0) { error = "invalid time"; return false; }
    if (!(std::isfinite(c.open) && std::isfinite(c.high) && std::isfinite(c.low) && std::isfinite(c.close)) || c.open <= 0 || c.high <= 0 || c.low <= 0 || c.close <= 0) { error = "prices must be finite and positive"; return false; }
    if (c.high < c.open || c.high < c.close || c.low > c.open || c.low > c.close || c.low > c.high) { error = "invalid candle geometry"; return false; }
    if (c.has_volume && (!std::isfinite(c.volume) || c.volume < 0)) { error = "invalid volume"; return false; }
    return true;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    long long previous = 0;
    std::string line;
    std::size_t index = 0;
    std::cout << std::setprecision(17);
    while (std::getline(std::cin, line)) {
        if (line.find_first_not_of(" \t\r\n") == std::string::npos) { ++index; continue; }
        Candle c{}; std::string error;
        if (!parse(line, c, error)) {
            std::cout << "{\"ok\":false,\"index\":" << index << ",\"error\":\"" << error << "\"}\n";
        } else if (c.time <= previous) {
            std::cout << "{\"ok\":false,\"index\":" << index << ",\"error\":\"timestamp must be strictly increasing\"}\n";
        } else {
            previous = c.time;
            std::cout << "{\"ok\":true,\"index\":" << index << ",\"time\":" << c.time << ",\"open\":" << c.open << ",\"high\":" << c.high << ",\"low\":" << c.low << ",\"close\":" << c.close;
            if (c.has_volume) std::cout << ",\"volume\":" << c.volume;
            std::cout << "}\n";
        }
        ++index;
    }
}
