import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useWorkspace } from "../context/use-workspace";
import { useAllWorkspaces } from "../../core/hooks/use-all-workspaces";
import { useRuntimeConfig } from "../context/use-runtime-config";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faChevronDown, faLayerGroup } from "@fortawesome/free-solid-svg-icons";

export function WorkspacePicker() {
  const config = useRuntimeConfig();
  const { selectedWorkspace, setSelectedWorkspace } = useWorkspace();
  const { allWorkspaces } = useAllWorkspaces();
  const [isOpen, setIsOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent);

  const filteredWorkspaces = useMemo(() => {
    if (!allWorkspaces) return [];
    if (!filter) return allWorkspaces;
    return allWorkspaces.filter((ws) => ws.name.toLowerCase().includes(filter.toLowerCase()));
  }, [allWorkspaces, filter]);

  const handleSelect = useCallback(
    (workspace: string | null) => {
      setSelectedWorkspace(workspace);
      setIsOpen(false);
      setFilter("");
    },
    [setSelectedWorkspace],
  );

  // Auto-focus search input when dropdown opens
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isOpen]);

  // Click outside to close
  useEffect(() => {
    const handleMouseDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setFilter("");
      }
    };

    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, []);

  // Keyboard shortcut (Ctrl+K / Cmd+K) and Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen((prev) => {
          if (prev) setFilter("");
          return !prev;
        });
      }
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
        setFilter("");
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  if (!config.workspaces_enabled) return null;

  const displayName = selectedWorkspace ?? "All Workspaces";

  return (
    <div ref={containerRef} className="relative" data-testid="workspace-picker">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-3 py-1 text-sm rounded-md
          border border-btn-secondary-border dark:border-btn-secondary-border-dark
          bg-ui-bg dark:bg-ui-bg-dark
          text-text-primary dark:text-text-primary-dark
          hover:bg-bg-primary-hover dark:hover:bg-bg-primary-hover-dark
          transition-colors cursor-pointer"
        aria-label="Select workspace"
        aria-expanded={isOpen}
      >
        <FontAwesomeIcon icon={faLayerGroup} className="w-3.5 h-3.5" />
        <span className="max-w-[120px] truncate">{displayName}</span>
        <kbd className="hidden sm:inline-block ml-1 px-1 py-0.5 text-[10px] font-mono rounded border border-btn-secondary-border dark:border-btn-secondary-border-dark opacity-60">
          {isMac ? "⌘K" : "Ctrl+K"}
        </kbd>
        <FontAwesomeIcon
          icon={faChevronDown}
          className={`w-3 h-3 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-64 max-h-80 overflow-y-auto rounded-md shadow-lg border border-btn-secondary-border dark:border-btn-secondary-border-dark bg-ui-bg dark:bg-ui-bg-dark z-50">
          <input
            ref={searchInputRef}
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter workspaces..."
            className="w-full px-3 py-2 text-sm border-b border-btn-secondary-border dark:border-btn-secondary-border-dark bg-transparent focus:outline-none text-text-primary dark:text-text-primary-dark placeholder-text-primary dark:placeholder-text-primary-dark"
          />
          <div role="listbox">
            <div
              role="option"
              tabIndex={0}
              aria-selected={!selectedWorkspace}
              onClick={() => handleSelect(null)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleSelect(null);
                }
              }}
              className={`px-3 py-2 text-sm cursor-pointer hover:bg-bg-primary-hover dark:hover:bg-bg-primary-hover-dark text-text-primary dark:text-text-primary-dark ${!selectedWorkspace ? "font-semibold" : ""}`}
            >
              All Workspaces {!selectedWorkspace && "✓"}
            </div>
            {filteredWorkspaces.map((ws) => (
              <div
                key={ws.name}
                role="option"
                tabIndex={0}
                aria-selected={selectedWorkspace === ws.name}
                onClick={() => handleSelect(ws.name)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handleSelect(ws.name);
                  }
                }}
                className={`px-3 py-2 text-sm cursor-pointer hover:bg-bg-primary-hover dark:hover:bg-bg-primary-hover-dark text-text-primary dark:text-text-primary-dark ${selectedWorkspace === ws.name ? "font-semibold" : ""}`}
              >
                {ws.name} {selectedWorkspace === ws.name && "✓"}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
