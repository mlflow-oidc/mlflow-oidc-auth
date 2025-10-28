import React from "react";

interface NavLinkProps extends React.PropsWithChildren {
  href: string;
  onClick?: () => void;
}

const NavLink: React.FC<NavLinkProps> = ({ href, children, onClick }) => {
  const baseClasses =
    "p-2 w-full sm:w-auto text-text-primary hover:text-text-primary-hover dark:text-text-primary-dark dark:hover:text-text-primary-hover-dark text-lg sm:text-sm font-medium transition-colors text-left sm:text-center rounded-md";
  return (
    <a href={href} className={baseClasses} onClick={onClick}>
      {children}
    </a>
  );
};

export default NavLink;
