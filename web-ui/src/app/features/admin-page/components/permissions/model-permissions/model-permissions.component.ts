import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { ModelsDataService } from 'src/app/shared/services';
import { TableActionEvent, TableActionModel } from 'src/app/shared/components/table/table.interface';
import { MODEL_COLUMN_CONFIG, MODEL_TABLE_ACTIONS } from './model-permissions.config';
import { TableActionEnum } from 'src/app/shared/components/table/table.config';
import { ModelModel } from 'src/app/shared/interfaces/models-data.interface';
import { AdminPageRoutesEnum } from '../../../config';
import { finalize } from 'rxjs';

@Component({
  selector: 'ml-model-permissions',
  templateUrl: './model-permissions.component.html',
  styleUrls: ['./model-permissions.component.scss'],
  standalone: false
})
export class ModelPermissionsComponent implements OnInit {
  columnConfig = MODEL_COLUMN_CONFIG;
  dataSource: ModelModel[] = [];
  actions: TableActionModel[] = MODEL_TABLE_ACTIONS;

  isLoading = false;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly modelDataService: ModelsDataService,
  ) {
  }

  ngOnInit(): void {
    this.isLoading = true;
    this.modelDataService.getAllModels()
      .pipe(
        finalize(() => this.isLoading = false),
      )
      .subscribe((models) => {
        this.dataSource = models;
      })
  }

  handleModelEdit({ name }: ModelModel) {
    this.router.navigate([`../${AdminPageRoutesEnum.MODEL}/` + name], { relativeTo: this.route })
  }

  handleAction({ action, item }: TableActionEvent<ModelModel>) {
    const actionMapping: { [key: string]: (item: ModelModel) => void } = {
      [TableActionEnum.EDIT]: this.handleModelEdit.bind(this),
    };

    const selectedAction = actionMapping[action.action];
    if (selectedAction) {
      selectedAction(item);
    }
  }
}
