import { TestBed } from "@angular/core/testing";
import {
  HttpClientTestingModule,
  HttpTestingController,
} from "@angular/common/http/testing";
import { PermissionDataService } from "../data/permission-data.service";
import { API_URL } from "src/app/core/configs/api-urls";
import { PermissionEnum } from "../../../core/configs/permissions";

describe("PermissionDataService", () => {
  let service: PermissionDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [PermissionDataService],
    });
    service = TestBed.inject(PermissionDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it("should be created", () => {
    expect(service).toBeTruthy();
  });

  it("should call createExperimentPermission with correct URL and payload", () => {
    const body = {
      experiment_id: "123",
      user_name: "testUser",
      permission: "READ",
    };
    service.createExperimentPermission(body).subscribe();
    const req = httpMock.expectOne(API_URL.CREATE_EXPERIMENT_PERMISSION);
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual(body);
  });

  it("should call updateExperimentPermission with correct URL and payload", () => {
    const body = {
      experiment_id: "123",
      user_name: "testUser",
      permission: "WRITE",
    };
    service.updateExperimentPermission(body).subscribe();
    const req = httpMock.expectOne(API_URL.UPDATE_EXPERIMENT_PERMISSION);
    expect(req.request.method).toBe("PATCH");
    expect(req.request.body).toEqual(body);
  });

  it("should call deleteExperimentPermission with correct URL and payload", () => {
    const body = { experiment_id: "123", user_name: "testUser" };
    service.deleteExperimentPermission(body).subscribe();
    const req = httpMock.expectOne(API_URL.DELETE_EXPERIMENT_PERMISSION);
    expect(req.request.method).toBe("DELETE");
    expect(req.request.body).toEqual(body);
  });

  it("should call createModelPermission with correct URL and payload", () => {
    const body = { name: "model1", user_name: "testUser", permission: "READ" };
    service.createModelPermission(body).subscribe();
    const req = httpMock.expectOne(API_URL.CREATE_MODEL_PERMISSION);
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual(body);
  });

  it("should call updateModelPermission with correct URL and payload", () => {
    const body = { name: "model1", user_name: "testUser", permission: "WRITE" };
    service.updateModelPermission(body).subscribe();
    const req = httpMock.expectOne(API_URL.UPDATE_MODEL_PERMISSION);
    expect(req.request.method).toBe("PATCH");
    expect(req.request.body).toEqual(body);
  });

  it("should call deleteModelPermission with correct URL and payload", () => {
    const body = { name: "model1", user_name: "testUser" };
    service.deleteModelPermission(body).subscribe();
    const req = httpMock.expectOne(API_URL.DELETE_MODEL_PERMISSION);
    expect(req.request.method).toBe("DELETE");
    expect(req.request.body).toEqual(body);
  });

  it("should call createPromptPermission with correct URL and payload", () => {
    const body = { name: "prompt1", user_name: "testUser", permission: "READ" };
    service.createPromptPermission(body).subscribe();
    const req = httpMock.expectOne(API_URL.CREATE_PROMPT_PERMISSION);
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual(body);
  });

  it("should call updatePromptPermission with correct URL and payload", () => {
    const body = {
      name: "prompt1",
      user_name: "testUser",
      permission: "WRITE",
    };
    service.updatePromptPermission(body).subscribe();
    const req = httpMock.expectOne(API_URL.UPDATE_PROMPT_PERMISSION);
    expect(req.request.method).toBe("PATCH");
    expect(req.request.body).toEqual(body);
  });

  it("should call deletePromptPermission with correct URL and payload", () => {
    const body = { name: "prompt1", user_name: "testUser" };
    service.deletePromptPermission(body).subscribe();
    const req = httpMock.expectOne(API_URL.DELETE_PROMPT_PERMISSION);
    expect(req.request.method).toBe("DELETE");
    expect(req.request.body).toEqual(body);
  });

  it("should call addExperimentPermissionToGroup with correct URL and payload", () => {
    const groupName = "group1";
    const experiment_id = "123";
    const permission = PermissionEnum.READ;
    service
      .addExperimentPermissionToGroup(groupName, experiment_id, permission)
      .subscribe();
    const req = httpMock.expectOne(
      API_URL.CREATE_GROUP_EXPERIMENT_PERMISSION.replace(
        "${groupName}",
        groupName,
      ),
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({ experiment_id, permission });
  });

  it("should call addModelPermissionToGroup with correct URL and payload", () => {
    const modelName = "model1";
    const groupName = "group1";
    const permission = "READ";
    service
      .addModelPermissionToGroup(modelName, groupName, permission)
      .subscribe();
    const req = httpMock.expectOne(
      API_URL.CREATE_GROUP_MODEL_PERMISSION.replace("${groupName}", groupName),
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({ model_name: modelName, permission });
  });

  it("should call addPromptPermissionToGroup with correct URL and payload", () => {
    const promptName = "prompt1";
    const groupName = "group1";
    const permission = "READ";
    service
      .addPromptPermissionToGroup(promptName, groupName, permission)
      .subscribe();
    const req = httpMock.expectOne(
      API_URL.CREATE_GROUP_PROMPT_PERMISSION.replace("${groupName}", groupName),
    );
    expect(req.request.method).toBe("POST");
    expect(req.request.body).toEqual({ prompt_name: promptName, permission });
  });

  it("should call removeExperimentPermissionFromGroup with correct URL and payload", () => {
    const groupName = "group1";
    const experiment_id = "123";
    service
      .removeExperimentPermissionFromGroup(groupName, experiment_id)
      .subscribe();
    const req = httpMock.expectOne(
      API_URL.DELETE_GROUP_EXPERIMENT_PERMISSION.replace(
        "${groupName}",
        groupName,
      ),
    );
    expect(req.request.method).toBe("DELETE");
    expect(req.request.body).toEqual({ experiment_id });
  });

  it("should call removeModelPermissionFromGroup with correct URL and payload", () => {
    const modelName = "model1";
    const groupName = "group1";
    service.removeModelPermissionFromGroup(modelName, groupName).subscribe();
    const req = httpMock.expectOne(
      API_URL.DELETE_GROUP_MODEL_PERMISSION.replace("${groupName}", groupName),
    );
    expect(req.request.method).toBe("DELETE");
    expect(req.request.body).toEqual({ model_name: modelName });
  });

  it("should call removePromptPermissionFromGroup with correct URL and payload", () => {
    const promptName = "prompt1";
    const groupName = "group1";
    service.removePromptPermissionFromGroup(promptName, groupName).subscribe();
    const req = httpMock.expectOne(
      API_URL.DELETE_GROUP_PROMPT_PERMISSION.replace("${groupName}", groupName),
    );
    expect(req.request.method).toBe("DELETE");
    expect(req.request.body).toEqual({ prompt_name: promptName });
  });

  it("should call updateExperimentPermissionForGroup with correct URL and payload", () => {
    const groupName = "group1";
    const experiment_id = "123";
    const permission = "WRITE";
    service
      .updateExperimentPermissionForGroup(groupName, experiment_id, permission)
      .subscribe();
    const req = httpMock.expectOne(
      API_URL.UPDATE_GROUP_EXPERIMENT_PERMISSION.replace(
        "${groupName}",
        groupName,
      ),
    );
    expect(req.request.method).toBe("PATCH");
    expect(req.request.body).toEqual({ experiment_id, permission });
  });

  it("should call updateModelPermissionForGroup with correct URL and payload", () => {
    const modelName = "model1";
    const groupName = "group1";
    const permission = "WRITE";
    service
      .updateModelPermissionForGroup(modelName, groupName, permission)
      .subscribe();
    const req = httpMock.expectOne(
      API_URL.UPDATE_GROUP_MODEL_PERMISSION.replace("${groupName}", groupName),
    );
    expect(req.request.method).toBe("PATCH");
    expect(req.request.body).toEqual({ model_name: modelName, permission });
  });

  it("should call updatePromptPermissionForGroup with correct URL and payload", () => {
    const promptName = "prompt1";
    const groupName = "group1";
    const permission = "WRITE";
    service
      .updatePromptPermissionForGroup(promptName, groupName, permission)
      .subscribe();
    const req = httpMock.expectOne(
      API_URL.UPDATE_GROUP_PROMPT_PERMISSION.replace("${groupName}", groupName),
    );
    expect(req.request.method).toBe("PATCH");
    expect(req.request.body).toEqual({ prompt_name: promptName, permission });
  });
});
