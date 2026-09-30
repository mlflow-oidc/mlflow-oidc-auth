/**
 * Install an in-memory `window.localStorage` (the test runtime does not always provide one) and
 * return it so tests can spy on or clear it.
 */
export function installLocalStorageMock(): Storage {
  let store = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return store.size;
    },
    clear: () => {
      store = new Map();
    },
    getItem: (key) => store.get(key) ?? null,
    key: (index) => Array.from(store.keys())[index] ?? null,
    removeItem: (key) => {
      store.delete(key);
    },
    setItem: (key, value) => {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(window, "localStorage", {
    value: storage,
    configurable: true,
    writable: true,
  });
  return storage;
}
