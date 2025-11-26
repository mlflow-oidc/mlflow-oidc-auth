import { useTheme } from "../utils/theme-utils";
import { faMoon, faSun } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";

const DarkModeToggle: React.FC = () => {
  const { isDark, toggleTheme } = useTheme();

  const buttonClasses = `
    flex items-center justify-center space-x-2 px-2 py-2 rounded transition-colors duration-200 cursor-pointer fill-current text-text-primary hover:text-text-primary-hover hover:bg-bg-primary-hover dark:text-text-primary-dark dark:hover:text-text-primary-hover-dark dark:hover:bg-bg-primary-hover-dark
  `;

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={buttonClasses}
      title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
      aria-label={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
    >
      <FontAwesomeIcon icon={isDark ? faMoon : faSun} size="1x" />
    </button>
  );
};

export default DarkModeToggle;
