#include <string>

struct Packet {
    int id;

    bool valid() const {
        return id > 0;
    }
};

class Parser {
public:
    std::string parse(const Packet& packet) {
        if (packet.valid()) {
            return "ok";
        }
        return "bad";
    }
};

int add(int a, int b) {
    return a + b;
}
