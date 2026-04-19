// Fixture for ast_chunker JS tests.

function topLevelFn(a, b) {
    return a + b;
}

const arrowFn = async (x) => {
    const y = x * 2;
    return y;
};

class Greeter {
    constructor(name) {
        this.name = name;
    }

    greet() {
        return `hello ${this.name}`;
    }
}

export function exportedFn() {
    // Note: braces in strings should not confuse the matcher: "{ not a block }"
    return 42;
}
