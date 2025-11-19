import SunIcon from "../../icons/sun-icon";
import MoonIcon from "../../icons/moon-icon";
import { useTheme } from "../../utils/theme-utils";

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
      {isDark ? (
        <MoonIcon className="w-4 h-5" />
      ) : (
        <SunIcon className="w-4 h-5" />
      )}
    </button>
  );
};

export default DarkModeToggle;
