export type ColumnConfig<T extends Record<string, unknown>> = {
  header: React.ReactNode;
  id?: string;
  render: (item: T) => React.ReactNode;
  className?: string;
};

export type Identifiable = { id?: string | number };

export type PrimitiveMode = {
  mode: "primitive";
  data: string[];
  searchTerm: string;
};

export type ObjectMode<T extends Identifiable & Record<string, unknown>> = {
  mode: "object";
  data: T[];
  columns: ColumnConfig<T>[];
  searchTerm: string;
};

export interface ObjectTableRowProps<
  T extends Identifiable & Record<string, unknown>,
> {
  item: T;
  columns: ColumnConfig<T>[];
  fallbackKey: string | number;
  index: number;
}

export type EntityListTableProps<
  T extends Identifiable & Record<string, unknown>,
> = PrimitiveMode | ObjectMode<T>;
