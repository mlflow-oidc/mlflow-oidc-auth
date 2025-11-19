import React from "react";
import { type NavigationData } from "./navigation-data";
import AppLink from "../app-link";

interface HeaderMobileNavProps extends NavigationData {
  isMenuOpen: boolean;
  onLinkClick: () => void;
}

const HeaderMobileNav: React.FC<HeaderMobileNavProps> = ({
  isMenuOpen,
  onLinkClick,
  mainLinks,
  userControls,
}) => {
  const linkClasses =
    "p-2 w-full sm:w-auto text-text-primary hover:text-text-primary-hover dark:text-text-primary-dark dark:hover:text-text-primary-hover-dark text-lg sm:text-sm font-medium transition-colors text-left sm:text-center rounded-md";
  return (
    <div
      id="mobile-menu"
      className={`
        fixed inset-0 pt-[48px] p-4 sm:hidden z-2 transition-transform duration-300 ease-in-out bg-ui-secondary-bg dark:bg-ui-secondary-bg-dark
          ${isMenuOpen ? "translate-x-0" : "translate-x-full"} 
      `}
    >
      <div className="flex flex-col space-y-4">
        <nav className="flex flex-col sm:flex-row space-y-2 sm:space-y-0">
          {mainLinks.map((link) => (
            <AppLink
              key={link.label}
              href={link.href}
              onClick={onLinkClick}
              isInternalLink={link.isInternalLink}
              className={linkClasses}
            >
              {link.label}
            </AppLink>
          ))}
        </nav>

        <div className="h-0 border-t border-gray-300 dark:border-gray-700"></div>

        <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0">
          {userControls.map((link) => (
            <AppLink
              key={link.label}
              href={link.href}
              onClick={onLinkClick}
              isInternalLink={link.isInternalLink}
              className={linkClasses}
            >
              {link.label}
            </AppLink>
          ))}
        </div>
      </div>
    </div>
  );
};

export default HeaderMobileNav;
