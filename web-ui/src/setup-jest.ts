import { setupZoneTestEnv } from 'jest-preset-angular/setup-env/zone';

setupZoneTestEnv();

// Define globals that are used by Angular
// Jest runs in jsdom which doesn't implement these
global.setTimeout = global.setTimeout || ((fn: Function) => fn());
global.queueMicrotask = global.queueMicrotask || ((fn: Function) => Promise.resolve().then(() => fn()));

jest.useFakeTimers({ legacyFakeTimers: false }); // Ensure modern fake timers

Object.defineProperty(window, 'CSS', { value: null });
Object.defineProperty(window, 'getComputedStyle', {
  value: () => {
    return {
      display: 'none',
      appearance: ['-webkit-appearance'],
    };
  },
});

Object.defineProperty(document, 'doctype', {
  value: '<!DOCTYPE html>',
});
Object.defineProperty(document.body.style, 'transform', {
  value: () => {
    return {
      enumerable: true,
      configurable: true,
    };
  },
});
