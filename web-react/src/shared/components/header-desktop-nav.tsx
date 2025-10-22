import React from "react";
import NavLink from "./nav-link";
import { type NavigationData } from "./navigation-data";

const HeaderDesktopNav: React.FC<NavigationData> = ({
  mainLinks,
  userControls,
}) => {
  return (
    <div className="hidden sm:flex justify-between items-center">
      <nav className="flex flex-col sm:flex-row space-y-2 sm:space-y-0">
        {mainLinks.map((link) => (
          <NavLink key={link.label} href={link.href}>
            {link.label}
          </NavLink>
        ))}
      </nav>
      <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0">
        {userControls.map((link) => (
          <NavLink key={link.label} href={link.href}>
            {link.label}
          </NavLink>
        ))}
      </div>
    </div>
  );
};

export default HeaderDesktopNav;
