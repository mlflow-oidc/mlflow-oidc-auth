import React from "react";
import { type NavigationData } from "./navigation-data";
import { AppLink } from "./app-link";

const HeaderDesktopNav: React.FC<NavigationData> = ({
  mainLinks,
  userControls,
}) => {
  const linkClasses =
    "p-2 w-full sm:w-auto text-text-primary hover:text-text-primary-hover dark:text-text-primary-dark dark:hover:text-text-primary-hover-dark text-sm font-medium transition-colors text-left sm:text-center rounded-md";
  return (
    <div className="hidden sm:flex justify-between items-center">
      <nav className="flex flex-col sm:flex-row space-y-2 sm:space-y-0">
        {mainLinks.map((link) => (
          <AppLink
            key={link.label}
            href={link.href}
            isInternalLink={link.isInternalLink}
            className={linkClasses}
          >
            {link.label}
          </AppLink>
        ))}
      </nav>
      <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0">
        {userControls.map((link) => (
          <AppLink
            key={link.label}
            href={link.href}
            isInternalLink={link.isInternalLink}
            className={linkClasses}
          >
            {link.label}
          </AppLink>
        ))}
      </div>
    </div>
  );
};

export default HeaderDesktopNav;
