import { useState, useEffect, useCallback } from "react";

// PRIMARY SOURCE OF TRUTH (controls theme state):
export const DARK_MODE_TOGGLE_ENABLED_KEY = "_mlflow_dark_mode_toggle_enabled"; // 'false' / 'true'
// SECONDARY SHADOW KEY (reflects theme state):
export const THEME_PREF_KEY = "databricks-dark-mode-pref"; // 'light' / 'dark'

export const applyTheme = (isDark: boolean) => {
  if (isDark) {
    document.documentElement.classList.add("dark");
    localStorage.setItem(DARK_MODE_TOGGLE_ENABLED_KEY, "true");
    localStorage.setItem(THEME_PREF_KEY, "dark");
  } else {
    document.documentElement.classList.remove("dark");
    localStorage.setItem(DARK_MODE_TOGGLE_ENABLED_KEY, "false");
    localStorage.setItem(THEME_PREF_KEY, "light");
  }
};

export const getInitialIsDarkState = (): boolean => {
  const initialIsDark = localStorage.getItem(DARK_MODE_TOGGLE_ENABLED_KEY);
  let isDarkState: boolean;

  if (initialIsDark === "true") {
    isDarkState = true;
  } else if (initialIsDark === "false") {
    isDarkState = false;
  } else {
    isDarkState = window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  return isDarkState;
};

export const initializeTheme = () => {
  const initialIsDark = getInitialIsDarkState();
  applyTheme(initialIsDark);
};

// A custom hook to manage the theme state within a component.
export const useTheme = () => {
  const [isDark, setIsDark] = useState(getInitialIsDarkState);

  useEffect(() => {
    applyTheme(isDark);
  }, [isDark]);

  const toggleTheme = useCallback(() => {
    setIsDark((prev) => !prev);
  }, []);

  return { isDark, toggleTheme };
};
