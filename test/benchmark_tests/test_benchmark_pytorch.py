# coding=utf-8
# Copyright 2018-2022 EVA
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest

from eva.server.command_handler import execute_query_fetch_all


@pytest.mark.torchtest
@pytest.mark.benchmark(
    warmup=False,
    warmup_iterations=1,
    min_rounds=1,
)
@pytest.mark.notparallel
def test_should_run_pytorch_and_yolo(benchmark, setup_pytorch_tests):
    select_query = """SELECT Yolo(data) FROM MyVideo
                    WHERE id < 5;"""
    actual_batch = benchmark(execute_query_fetch_all, select_query)
    assert len(actual_batch) == 5


@pytest.mark.torchtest
@pytest.mark.benchmark(
    warmup=False,
    warmup_iterations=1,
    min_rounds=1,
)
@pytest.mark.notparallel
def test_should_run_pytorch_and_facenet(benchmark, setup_pytorch_tests):
    create_udf_query = """CREATE UDF IF NOT EXISTS FaceDetector
                INPUT  (frame NDARRAY UINT8(3, ANYDIM, ANYDIM))
                OUTPUT (bboxes NDARRAY FLOAT32(ANYDIM, 4),
                        scores NDARRAY FLOAT32(ANYDIM))
                TYPE  FaceDetection
                IMPL  'eva/udfs/face_detector.py';
    """
    execute_query_fetch_all(create_udf_query)

    select_query = """SELECT FaceDetector(data) FROM MyVideo
                    WHERE id < 5;"""

    actual_batch = benchmark(execute_query_fetch_all, select_query)
    assert len(actual_batch) == 5


@pytest.mark.torchtest
@pytest.mark.benchmark(
    warmup=False,
    warmup_iterations=1,
    min_rounds=1,
)
@pytest.mark.notparallel
def test_should_run_pytorch_and_resnet50(benchmark, setup_pytorch_tests):
    create_udf_query = """CREATE UDF IF NOT EXISTS FeatureExtractor
                INPUT  (frame NDARRAY UINT8(3, ANYDIM, ANYDIM))
                OUTPUT (features NDARRAY FLOAT32(ANYDIM))
                TYPE  Classification
                IMPL  'eva/udfs/feature_extractor.py';
    """
    execute_query_fetch_all(create_udf_query)

    select_query = """SELECT FeatureExtractor(data) FROM MyVideo
                    WHERE id < 5;"""
    actual_batch = benchmark(execute_query_fetch_all, select_query)
    assert len(actual_batch) == 5

    # non-trivial test case for Resnet50
    res = actual_batch.frames
    assert res["featureextractor.features"][0].shape == (1, 2048)
    # assert res["featureextractor.features"][0][0][0] > 0.3


@pytest.mark.torchtest
@pytest.mark.benchmark(
    warmup=False,
    warmup_iterations=1,
    min_rounds=1,
)
@pytest.mark.notparallel
def test_lateral_join(benchmark, setup_pytorch_tests):
    select_query = """SELECT id, a FROM MyVideo JOIN LATERAL
                    Yolo(data) AS T(a,b,c) WHERE id < 5;"""
    actual_batch = benchmark(execute_query_fetch_all, select_query)
    assert len(actual_batch) == 5
    assert list(actual_batch.columns) == ["myvideo.id", "T.a"]


@pytest.mark.benchmark(
    warmup=False,
    warmup_iterations=1,
    min_rounds=1,
)
def test_automatic_speech_recognition(benchmark, setup_pytorch_tests):
    udf_name = "SpeechRecognizer"
    create_udf = (
        f"CREATE UDF {udf_name} TYPE HuggingFace "
        "'task' 'automatic-speech-recognition' 'model' 'openai/whisper-base';"
    )
    execute_query_fetch_all(create_udf)

    # TODO: use with SAMPLE AUDIORATE 16000
    select_query = f"SELECT {udf_name}(audio) FROM VIDEOS;"
    output = benchmark(execute_query_fetch_all, select_query)

    # verify that output has one row and one column only
    assert output.frames.shape == (1, 1)
    # verify that speech was converted to text correctly
    assert output.frames.iloc[0][0].count("touchdown") == 2

    drop_udf_query = f"DROP UDF {udf_name};"
    execute_query_fetch_all(drop_udf_query)


@pytest.mark.benchmark(
    warmup=False,
    warmup_iterations=1,
    min_rounds=1,
)
def test_summarization_from_video(benchmark, setup_pytorch_tests):
    asr_udf = "SpeechRecognizer"
    create_udf = (
        f"CREATE UDF {asr_udf} TYPE HuggingFace "
        "'task' 'automatic-speech-recognition' 'model' 'openai/whisper-base';"
    )
    execute_query_fetch_all(create_udf)

    summary_udf = "Summarizer"
    create_udf = (
        f"CREATE UDF {summary_udf} TYPE HuggingFace "
        "'task' 'summarization' 'model' 'philschmid/bart-large-cnn-samsum' 'min_length' 10 'max_length' 100;"
    )
    execute_query_fetch_all(create_udf)

    # TODO: use with SAMPLE AUDIORATE 16000
    select_query = f"SELECT {summary_udf}({asr_udf}(audio)) FROM VIDEOS;"
    output = benchmark(execute_query_fetch_all, select_query)

    # verify that output has one row and one column only
    assert output.frames.shape == (1, 1)
    # verify that summary is as expected
    assert (
        output.frames.iloc[0][0]
        == "Jalen Hurts has scored his second rushing touchdown of the game."
    )

    drop_udf_query = f"DROP UDF {asr_udf};"
    execute_query_fetch_all(drop_udf_query)
    drop_udf_query = f"DROP UDF {summary_udf};"
    execute_query_fetch_all(drop_udf_query)
