# Copyright 2023 Avaiga Private Limited
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
# an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.

import datetime
import traceback
from unittest import mock

import pytest

from src.taipy.core._orchestrator._orchestrator import _Orchestrator
from src.taipy.core.data._data_manager import _DataManager
from src.taipy.core.data._data_manager_factory import _DataManagerFactory
from src.taipy.core.data.csv import CSVDataNode
from src.taipy.core.data.data_node_id import DataNodeId, Edit
from src.taipy.core.exceptions.exceptions import ModelNotFound
from src.taipy.core.job._job_manager_factory import _JobManagerFactory
from src.taipy.core.job._job_model import _JobModel
from src.taipy.core.job.job import Job
from src.taipy.core.job.job_id import JobId
from src.taipy.core.job.status import Status
from src.taipy.core.task._task_manager import _TaskManager
from src.taipy.core.task._task_manager_factory import _TaskManagerFactory
from src.taipy.core.task.task import Task
from src.taipy.core.task.task_id import TaskId
from taipy.config.common.scope import Scope
from taipy.config.config import Config

data_node = CSVDataNode(
    "test_data_node",
    Scope.SCENARIO,
    DataNodeId("dn_id"),
    "name",
    "owner_id",
    {"task_id"},
    datetime.datetime(1985, 10, 14, 2, 30, 0),
    [Edit(dict(timestamp=datetime.datetime(1985, 10, 14, 2, 30, 0), job_id="job_id"))],
    "latest",
    None,
    False,
    {"path": "/path", "has_header": True},
)

task = Task("config_id", {}, print, [data_node], [], TaskId("task_id"), owner_id="owner_id", version="latest")


def f():
    pass


class A:
    class B:
        def f(self):
            pass

    def f(self):
        pass

    @classmethod
    def g(cls):
        pass

    @staticmethod
    def h():
        pass


job = Job(JobId("id"), task, "submit_id", "submit_entity_id", version="latest")
job._subscribers = [f, A.f, A.g, A.h, A.B.f]
job._exceptions = [traceback.TracebackException.from_exception(Exception())]

job_model = _JobModel(
    id=JobId("id"),
    task_id=task.id,
    status=Status(Status.SUBMITTED),
    force=False,
    submit_id="submit_id",
    submit_entity_id="submit_entity_id",
    creation_date=job._creation_date.isoformat(),
    subscribers=Job._serialize_subscribers(job._subscribers),
    stacktrace=job._stacktrace,
    version="latest",
)


class TestJobRepository:
    def test_save_and_load(self, tmpdir):
        repository = _JobManagerFactory._build_repository()
        repository.base_path = tmpdir
        repository._save(job)
        with pytest.raises(ModelNotFound):
            repository._load("id")
        _DataManager._set(data_node)
        _TaskManager._set(task)
        j = repository._load("id")
        assert j.id == job.id

    def test_save_and_load_with_sql_repo(self):
        Config.configure_global_app(repository_type="sql")

        _DataManagerFactory._build_manager()._delete_all()
        _TaskManagerFactory._build_manager()._delete_all()

        repository = _JobManagerFactory._build_repository()
        repository._delete_all()

        repository._save(job)
        with pytest.raises(ModelNotFound):
            repository._load("id")
        _DataManager._set(data_node)
        _TaskManager._set(task)
        j = repository._load("id")
        assert j.id == job.id

    def test_from_model_version_2_2(self):
        _TaskManagerFactory._build_repository()._save(Task("task_config_id", {}, print, id="tid"))
        repository = _JobManagerFactory._build_repository()
        subscribers = [
            {
                "fct_name": "_Scheduler._on_status_change",
                "fct_params": [],
                "fct_module": "taipy.core._scheduler._scheduler",
            }
        ]
        job_model = _JobModel(
            JobId("jid"),
            "tid",
            Status.COMPLETED,
            False,
            "sid",
            "seid",
            datetime.datetime.now().isoformat(),
            subscribers,
            [],
            "version",
        )
        with mock.patch.object(_JobModel, "from_dict") as from_dict_mck:
            from_dict_mck.return_value = job_model
            with mock.patch("src.taipy.core.job._job_converter._load_fct") as mck:
                mck.return_value = _Orchestrator._on_status_change
                job = repository.converter._model_to_entity(job_model)
                assert job._subscribers[0] == _Orchestrator._on_status_change
                repository._save(job)
        job = repository._load("jid")
        assert job._subscribers[0] == _Orchestrator._on_status_change
