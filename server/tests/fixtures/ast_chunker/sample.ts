// Fixture for ast_chunker TS tests.

export interface User {
    id: number;
    name: string;
}

export function makeUser(id: number, name: string): User {
    return { id, name };
}

const upper = (s: string): string => {
    return s.toUpperCase();
};

export class UserService {
    private cache: Map<number, User> = new Map();

    public getUser(id: number): User | undefined {
        return this.cache.get(id);
    }
}
