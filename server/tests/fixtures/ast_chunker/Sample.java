package com.example.fixtures;

public class Sample {

    private int counter;

    public Sample(int initial) {
        this.counter = initial;
    }

    public int increment() {
        this.counter += 1;
        return this.counter;
    }

    private static String describe(int value) {
        return "value=" + value;
    }
}

interface Greeter {
    String greet(String name);
}
