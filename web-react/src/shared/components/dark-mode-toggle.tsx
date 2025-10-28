import { useEffect, useState, useCallback } from "react";
import SunIcon from "../icons/sun-icon";
import MoonIcon from "../icons/moon-icon";

// PRIMARY SOURCE OF TRUTH (controls theme state):
const DARK_MODE_TOGGLE_ENABLED_KEY = "_mlflow_dark_mode_toggle_enabled"; // 'false' / 'true'
// SECONDARY SHADOW KEY (reflects theme state):
const THEME_PREF_KEY = "databricks-dark-mode-pref"; // 'light' / 'dark'

const applyTheme = (isDark: boolean) => {
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

const initializeIsDarkState = () => {
  const initialIsDark = localStorage.getItem(DARK_MODE_TOGGLE_ENABLED_KEY);
  let isDarkState: boolean;

  if (initialIsDark === "true") {
    isDarkState = true;
  } else if (initialIsDark === "false") {
    isDarkState = false;
  } else {
    isDarkState = window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  applyTheme(isDarkState);

  return isDarkState;
};

const DarkModeToggle: React.FC = () => {
  const [isDark, setIsDark] = useState(initializeIsDarkState);

  useEffect(() => {
    applyTheme(isDark);
  }, [isDark]);

  const toggleDarkMode = useCallback(() => {
    setIsDark((prev) => !prev);
  }, []);

  const buttonClasses = `
    flex items-center justify-center space-x-2 px-2 py-2 rounded transition-colors duration-200 cursor-pointer fill-current text-text-primary hover:text-text-primary-hover hover:bg-bg-primary-hover dark:text-text-primary-dark dark:hover:text-text-primary-hover-dark dark:hover:bg-bg-primary-hover-dark
  `;

  return (
    <button
      type="button"
      onClick={toggleDarkMode}
      className={buttonClasses}
      title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
      aria-label={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
    >
      {isDark ? (
        <MoonIcon className="w-4 h-5" />
      ) : (
        <SunIcon className="w-4 h-5" />
      )}
    </button>
  );
};

export default DarkModeToggle;
