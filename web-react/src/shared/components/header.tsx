import DarkModeToggle from "./dark-mode-toggle";
import { Link } from "react-router";

interface HeaderProps {
  userName?: string;
}

const NavLink: React.FC<React.PropsWithChildren<{ href: string }>> = ({
  href,
  children,
}) => {
  const baseClasses =
    "px-2 py-2 text-[rgb(95,114,129)] hover:text-[rgb(14,83,139)] dark:text-[rgb(146,164,179)] dark:hover:text-[rgb(138,202,255)] text-sm font-medium transition-colors";
  return (
    <a href={href} className={baseClasses}>
      {children}
    </a>
  );
};

const Header: React.FC<HeaderProps> = ({ userName = "User" }) => {
  return (
    <header
      className="
        p-2 shadow-md flex justify-between items-center
        bg-[rgb(246,247,249)] dark:bg-[rgb(31,39,45)]
      "
    >
      {/* 1. Left - Logo Placeholder */}
      <div className="flex items-center space-x-4">
        {/* Placeholder for a logo/home link */}
        <Link to="/" className="text-xl font-extrabold text-[#2374bb]">
          MlflowOidcAuth
        </Link>
      </div>

      {/* 2. Center - Main Navigation Links */}
      <nav className="flex space-x-6">
        <NavLink href="#">MLFlow</NavLink>
        <NavLink href="#">GitHub</NavLink>
        <NavLink href="#">Docs</NavLink>
      </nav>

      {/* 3. Right - User Menu and Utility */}
      <div className="flex items-center space-x-4">
        <DarkModeToggle />
        <NavLink href="#">{`Hello, ${userName}`}</NavLink>
        <NavLink href="#">Logout</NavLink>
      </div>
    </header>
  );
};

export default Header;
