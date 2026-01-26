import { useTheme } from "../utils/theme-utils";
import { faMoon, faSun } from "@fortawesome/free-solid-svg-icons";
import { Button } from "./button";

const DarkModeToggle: React.FC = () => {
  const { isDark, toggleTheme } = useTheme();

  return (
    <Button
      variant="ghost"
      onClick={toggleTheme}
      title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
      aria-label={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
      icon={isDark ? faMoon : faSun}
      iconClassName="text-sm"
    />
  );
};

export default DarkModeToggle;
