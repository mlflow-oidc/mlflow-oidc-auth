import { useEffect, useState } from "react";
import { Link } from "react-router";
import DarkModeToggle from "./dark-mode-toggle";
import MenuIcon from "../icons/menu-icon";
import CloseIcon from "../icons/close-icon";

interface HeaderProps {
  userName?: string;
}

const NavLink: React.FC<
  React.PropsWithChildren<{ href: string; onClick?: () => void }>
> = ({ href, children, onClick }) => {
  const baseClasses =
    "p-2 w-full sm:w-auto text-[rgb(95,114,129)] hover:text-[rgb(14,83,139)] dark:text-[rgb(146,164,179)] dark:hover:text-[rgb(138,202,255)] text-lg sm:text-sm font-medium transition-colors text-left sm:text-center rounded-md";
  return (
    <a href={href} className={baseClasses} onClick={onClick}>
      {children}
    </a>
  );
};

const Header: React.FC<HeaderProps> = ({ userName = "User" }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const handleLinkClick = () => setIsMenuOpen(false);

  useEffect(() => {
    if (isMenuOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }

    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isMenuOpen]);

  const mainLinksData = [
    { label: "MLFlow", href: "#" },
    { label: "GitHub", href: "#" },
    { label: "Docs", href: "#" },
  ];

  const userControlsData = [
    { label: `Hello, ${userName}`, href: "#" },
    { label: "Logout", href: "#" },
  ];

  const mainNavLinks = (
    <nav className="flex flex-col sm:flex-row space-y-2 sm:space-y-0">
      {mainLinksData.map((link) => (
        <NavLink key={link.label} href={link.href} onClick={handleLinkClick}>
          {link.label}
        </NavLink>
      ))}
    </nav>
  );

  const userControls = (
    <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0">
      {userControlsData.map((link) => (
        <NavLink key={link.label} href={link.href} onClick={handleLinkClick}>
          {link.label}
        </NavLink>
      ))}
    </div>
  );

  return (
    <header className="p-2 shadow-md bg-[rgb(246,247,249)] dark:bg-[rgb(31,39,45)]">
      <div className="sticky z-3 flex justify-between items-center">
        <Link to="/" className="text-xl font-extrabold text-[#2374bb]">
          MlflowOidcAuth
        </Link>

        <div className="flex">
          <div className="flex items-center">
            <DarkModeToggle />
            <button
              type="button"
              className="sm:hidden fill-current text-[rgb(95,114,129)] hover:text-[rgb(14,83,139)] hover:bg-[rgba(34,114,180,0.08)] dark:text-[rgb(186,225,252)] dark:hover:text-[rgb(138,202,255)] dark:hover:bg-[rgba(138,202,255,0.08)] cursor-pointer p-1 rounded transition-colors"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              aria-expanded={isMenuOpen}
              aria-controls="mobile-menu"
            >
              {isMenuOpen ? <CloseIcon /> : <MenuIcon />}
            </button>
          </div>

          <div className="hidden sm:flex justify-between items-center">
            {mainNavLinks}
            {userControls}
          </div>
        </div>
      </div>

      <div
        id="mobile-menu"
        className={`
          fixed inset-0 pt-[48px] p-4 sm:hidden z-2 transition-transform duration-300 ease-in-out bg-[rgb(246,247,249)] dark:bg-[rgb(31,39,45)]
          ${isMenuOpen ? "translate-x-0" : "translate-x-full"} 
        `}
      >
        <div className="flex flex-col space-y-4">
          {mainNavLinks}
          <div className="h-0 border-t border-gray-300 dark:border-gray-700"></div>{" "}
          {userControls}
        </div>
      </div>
    </header>
  );
};

export default Header;
