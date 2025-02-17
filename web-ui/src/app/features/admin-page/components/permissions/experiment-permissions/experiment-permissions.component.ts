import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { ExperimentsDataService } from 'src/app/shared/services';
import { TableActionEvent, TableActionModel } from 'src/app/shared/components/table/table.interface';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import { COLUMN_CONFIG, TABLE_ACTIONS } from './experiment-permissions.config';
import { ExperimentModel } from 'src/app/shared/interfaces/experiments-data.interface';
import { AdminPageRoutesEnum } from '../../../config';
import { finalize } from 'rxjs';


@Component({
  selector: 'ml-experiment-permissions',
  templateUrl: './experiment-permissions.component.html',
  styleUrls: ['./experiment-permissions.component.scss'],
  standalone: false
})
export class ExperimentPermissionsComponent implements OnInit {
  columnConfig = COLUMN_CONFIG;
  dataSource: ExperimentModel[] = [];
  actions: TableActionModel[] = TABLE_ACTIONS;

  isLoading = false;

  constructor(
    private readonly router: Router,
    private readonly route: ActivatedRoute,
    private readonly experimentDataService: ExperimentsDataService,
  ) { }

  ngOnInit(): void {
    this.isLoading = true;
    this.experimentDataService.getAllExperiments()
      .pipe(
        finalize(() => this.isLoading = false),
      )
      .subscribe((experiments) => this.dataSource = experiments);
  }

  handleActions(event: TableActionEvent<ExperimentModel>) {
    const actionMapping: { [key: string]: (experiment: ExperimentModel) => void } = {
      [TableActionEnum.EDIT]: this.handleExperimentEdit.bind(this),
    }

    const selectedAction = actionMapping[event.action.action];
    if (selectedAction) {
      selectedAction(event.item);
    }
  }

  handleExperimentEdit({ id }: ExperimentModel) {
    this.router.navigate([`../${AdminPageRoutesEnum.EXPERIMENT}/` + id], { relativeTo: this.route })
  }
}
