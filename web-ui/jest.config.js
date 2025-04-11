globalThis.ngJest = {
  skipNgcc: true,
  tsconfig: "tsconfig.spec.json",
};

/** @type {import('@jest/types').Config.InitialOptions} */
module.exports = {
  preset: "jest-preset-angular",
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/src/setup-jest.ts"],
  transform: {
    "^.+\\.ts$": "ts-jest",
  },
  transformIgnorePatterns: ["/node_modules/(?!flat)/"],
  moduleDirectories: ["node_modules", "src"],
  moduleNameMapper: {
    "^src/(.*)$": "<rootDir>/src/$1",
    "\\.(css|scss)$": "identity-obj-proxy",
  },
  fakeTimers: {
    enableGlobally: true,
  },
};
