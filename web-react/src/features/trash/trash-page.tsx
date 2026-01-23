import { useState, useMemo, useEffect } from "react";
import { useParams, Link } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { useDeletedExperiments } from "../../core/hooks/use-deleted-experiments";
import { useDeletedRuns } from "../../core/hooks/use-deleted-runs";
import { useSearch } from "../../core/hooks/use-search";
import { Button } from "../../shared/components/button";
import { IconButton } from "../../shared/components/icon-button";
import { faUndo, faTrash } from "@fortawesome/free-solid-svg-icons";
import type { ColumnConfig } from "../../shared/types/table";
import type { DeletedExperiment, DeletedRun } from "../../shared/types/entity";
import { useToast } from "../../shared/components/toast/use-toast";
import { restoreExperiment, restoreRun, cleanupTrash } from "../../core/services/trash-service";
import { RemoveFromTrashModal } from "./remove-from-trash-modal";

type TrashTab = "experiments" | "runs";

interface TrashItem {
  id: string;
  name: string;
  creation: number;
  lastUpdate: number | null;
  original: DeletedExperiment | DeletedRun;
  type: TrashTab;
  [key: string]: unknown;
}

export default function TrashPage() {
  const { tab } = useParams<{ tab?: string }>();
  const activeTab: TrashTab = (tab === "runs" ? "runs" : "experiments");

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isProcessing, setIsProcessing] = useState(false);
  const { showToast } = useToast();
  const [itemsToDelete, setItemsToDelete] = useState<TrashItem[] | null>(null);

  useEffect(() => {
    setSelectedIds(new Set());
  }, [activeTab]);

  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const {
    deletedExperiments,
    isLoading: isExpLoading,
    error: expError,
    refresh: refreshExp,
  } = useDeletedExperiments();

  const {
    deletedRuns,
    isLoading: isRunsLoading,
    error: runsError,
    refresh: refreshRuns,
  } = useDeletedRuns();

  const isLoading = activeTab === "experiments" ? isExpLoading : isRunsLoading;
  const error = activeTab === "experiments" ? expError : runsError;
  const refresh = activeTab === "experiments" ? refreshExp : refreshRuns;

  const data: TrashItem[] = useMemo(() => {
    if (activeTab === "experiments") {
      return (deletedExperiments || []).map((e) => ({
        id: e.experiment_id,
        name: e.name,
        creation: e.creation_time,
        lastUpdate: e.last_update_time,
        original: e,
        type: "experiments",
      }));
    } else {
      return (deletedRuns || []).map((r) => ({
        id: r.run_id,
        name: r.run_name || `Run ${r.run_id}`,
        creation: r.start_time,
        lastUpdate: r.end_time,
        original: r,
        type: "runs",
      }));
    }
  }, [activeTab, deletedExperiments, deletedRuns]);

  const filteredData = useMemo(() => {
    return data.filter((item) =>
      item.name.toLowerCase().includes(submittedTerm.toLowerCase())
    );
  }, [data, submittedTerm]);

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(filteredData.map((item) => item.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleSelectOne = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedIds);
    if (checked) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    setSelectedIds(newSelected);
  };

  const handleRestore = async (ids: string[]) => {
    if (ids.length === 0) return;
    setIsProcessing(true);
    try {
      if (activeTab === "experiments") {
        await Promise.all(ids.map((id) => restoreExperiment(id)));
      } else {
        await Promise.all(ids.map((id) => restoreRun(id)));
      }
      showToast(`Successfully restored ${ids.length} item(s)`, "success");
      setSelectedIds(new Set());
      refresh();
    } catch {
      showToast("Failed to restore items", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDeleteClick = (ids: string[]) => {
    if (ids.length === 0) return;
    const items = data.filter((item) => ids.includes(item.id));
    setItemsToDelete(items);
  };

  const confirmDelete = async () => {
    if (!itemsToDelete || itemsToDelete.length === 0) return;
    setIsProcessing(true);
    const ids = itemsToDelete.map((item) => item.id);

    try {
      if (activeTab === "experiments") {
        await cleanupTrash({ experiment_ids: ids.join(",") });
      } else {
        await cleanupTrash({ run_ids: ids.join(",") });
      }
      showToast(`Successfully deleted ${ids.length} item(s)`, "success");
      setSelectedIds(new Set());
      setItemsToDelete(null);
      refresh();
    } catch {
      showToast("Failed to delete items", "error");
    } finally {
      setIsProcessing(false);
    }
  };

  const columns: ColumnConfig<TrashItem>[] = [
    {
      header: (
        <div className="flex items-center justify-center">
            <input
            type="checkbox"
            className="w-4 h-4 rounded custom-checkbox"
            checked={filteredData.length > 0 && selectedIds.size === filteredData.length}
            onChange={(e) => handleSelectAll(e.target.checked)}
            />
        </div>
      ),
      id: "select",
      render: (item) => (
        <div className="flex items-center justify-center">
            <input
            type="checkbox"
            className="w-4 h-4 rounded custom-checkbox"
            checked={selectedIds.has(item.id)}
            onChange={(e) => handleSelectOne(item.id, e.target.checked)}
            />
        </div>
      ),
      className: "w-8 m-[2px] flex-none",
    },
    {
      header: "Experiment ID",
      render: (item: TrashItem) => item.original.experiment_id,
    },
    {
      header: "Name",
      render: (item) => item.name,
    },
    {
      header: "Creation",
      render: (item) => new Date(item.creation).toLocaleString(),
    },
    {
      header: "Last Update",
      render: (item) =>
        item.lastUpdate ? new Date(item.lastUpdate).toLocaleString() : "-",
    },
    {
      header: "Actions",
      render: (item) => (
        <div className="flex space-x-2">
          <IconButton
            icon={faUndo}
            title="Restore"
            onClick={() => handleRestore([item.id])}
            disabled={isProcessing}
          />
          <IconButton
            icon={faTrash}
            title="Delete Permanently"
            onClick={() => handleDeleteClick([item.id])}
            disabled={isProcessing}
          />
        </div>
      ),
      className: "w-24",
    },
  ];

  return (
    <PageContainer title="Trash">
      <div className="flex justify-between items-center border-b border-btn-secondary-border dark:border-btn-secondary-border-dark mb-3">
        <div className="flex space-x-4">
          {[
            { id: "experiments", label: "Experiments" },
            { id: "runs", label: "Runs" },
          ].map((tab) => (
            <Link
              key={tab.id}
              to={`/trash/${tab.id}`}
              className={`py-2 px-4 border-b-2 font-medium text-sm transition-colors duration-200 ${
                activeTab === tab.id
                  ? "border-btn-primary text-btn-primary dark:border-btn-primary-dark dark:text-btn-primary-dark"
                  : "border-transparent text-text-primary dark:text-text-primary-dark hover:text-text-primary-hover dark:hover:text-text-primary-hover-dark hover:border-btn-secondary-border dark:hover:border-btn-secondary-border-dark"
              }`}
            >
              {tab.label}
            </Link>
          ))}
        </div>
      </div>

      <PageStatus
        isLoading={isLoading}
        loadingText={`Loading ${activeTab}...`}
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <div className="mt-2 mb-3 flex items-center justify-between gap-6">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder={`Search ${activeTab}...`}
            />
            <div className="flex space-x-2">
              <Button
                variant="secondary"
                onClick={() => handleRestore(Array.from(selectedIds))}
                disabled={selectedIds.size === 0 || isProcessing}
              >
                Restore
              </Button>
              <Button
                variant="danger"
                onClick={() => handleDeleteClick(Array.from(selectedIds))}
                disabled={selectedIds.size === 0 || isProcessing}
              >
                Delete
              </Button>
            </div>
          </div>

          <EntityListTable
            mode="object"
            data={filteredData}
            columns={columns}
            searchTerm={submittedTerm}
          />
        </>
      )}
      {itemsToDelete && (
        <RemoveFromTrashModal
          isOpen={!!itemsToDelete}
          onClose={() => setItemsToDelete(null)}
          onConfirm={confirmDelete}
          items={itemsToDelete}
          itemType={activeTab}
          isProcessing={isProcessing}
        />
      )}
    </PageContainer>
  );
}
