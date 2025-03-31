import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnInit,
  Output,
  SimpleChanges,
} from "@angular/core";
import {
  TableActionEvent,
  TableActionModel,
  TableColumnConfigModel,
} from "./table.interface";
import { MatTableDataSource } from "@angular/material/table";

@Component({
  selector: "ml-table",
  templateUrl: "./table.component.html",
  styleUrls: ["./table.component.scss"],
  standalone: false,
})
export class TableComponent<T> implements OnInit, OnChanges {
  @Input() columnConfig: TableColumnConfigModel[] = [];
  @Input() data: T[] = [];
  @Input() actions: TableActionModel[] = [];

  @Output() action = new EventEmitter<TableActionEvent<T>>();

  dataSource: MatTableDataSource<T> = new MatTableDataSource<T>();
  columns: string[] = [];

  serachValue: string = "";

  readonly columnActionName = "actions";

  ngOnChanges(changes: SimpleChanges): void {
    const data = changes["data"].currentValue;
    if (data) {
      this.dataSource = new MatTableDataSource(data);
    }
  }

  ngOnInit(): void {
    const columnKeys = this.columnConfig.map((config) => config.key);

    this.dataSource = new MatTableDataSource(this.data);
    this.columns = columnKeys;
    this.actions.length
      ? (this.columns = [this.columnActionName, ...columnKeys])
      : (this.columns = columnKeys);
  }

  filter(event: Event) {
    const inputElement = event.target as HTMLInputElement;
    this.dataSource.filter = inputElement.value.trim().toLowerCase();
  }

  handleActionClick(item: T, action: TableActionModel) {
    this.action.emit({ item, action });
  }
}
