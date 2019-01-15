import http.server
import json
import socketserver
import time
from base64 import b64encode
from copy import deepcopy
from threading import Thread

import pytest
from aria2p import JSONRPCClient, JSONRPCError
from aria2p.client import JSONRPC_CODES, JSONRPC_PARSER_ERROR
import requests
from responses import mock as responses

from . import (
    BUNSENLABS_MAGNET,
    BUNSENLABS_TORRENT,
    CONFIGS_DIR,
    DEBIAN_METALINK,
    SESSIONS_DIR,
    XUBUNTU_MIRRORS,
    Aria2Server,
)


# callback that return params of a single call as result
def call_params_callback(request):
    payload = json.loads(request.body)
    resp_body = {"result": payload["params"]}
    return 200, {}, json.dumps(resp_body)


# callback that return params of a batch call as result
def batch_call_params_callback(request):
    payload = json.loads(request.body)
    resp_body = [{"result": method["params"]} for method in payload]
    return 200, {}, json.dumps(resp_body)


@responses.activate
def test_call_raises_custom_error():
    client = JSONRPCClient()
    responses.add(responses.POST, client.server, json={"error": {"code": 1, "message": "Custom message"}}, status=200)
    with pytest.raises(JSONRPCError, match=r"Custom message") as e:
        client.call("aria2.method")
        assert e.code == 1


@responses.activate
def test_call_raises_known_error():
    client = JSONRPCClient()
    responses.add(
        responses.POST,
        client.server,
        json={"error": {"code": JSONRPC_PARSER_ERROR, "message": "Custom message"}},
        status=200,
    )
    with pytest.raises(JSONRPCError, match=rf"{JSONRPC_CODES[JSONRPC_PARSER_ERROR]}\nCustom message") as e:
        client.call("aria2.method")
        assert e.code == JSONRPC_PARSER_ERROR


@responses.activate
def test_insert_secret_with_aria2_method_call():
    # create client with secret
    secret = "hello"
    client = JSONRPCClient(secret=secret)

    responses.add_callback(responses.POST, client.server, callback=call_params_callback)

    # create params
    params = ["param1", "param2"]
    # copy params and insert secret
    expected_params = deepcopy(params)
    expected_params.insert(0, secret)

    # call function and assert result
    resp = client.call(client.ADD_URI, params, insert_secret=True)
    assert resp == expected_params


@responses.activate
def test_insert_secret_with_system_multicall():
    # create client with secret
    secret = "hello"
    client = JSONRPCClient(secret=secret)

    responses.add_callback(responses.POST, client.server, callback=call_params_callback)

    # create params
    params = [
        [
            {"methodName": client.ADD_URI, "params": ["param1", "param2"]},
            {"methodName": client.ADD_URI, "params": ["param3", "param4"]},
        ]
    ]
    # copy params and insert secret
    expected_params = deepcopy(params)
    for param in expected_params[0]:
        param["params"].insert(0, secret)

    # call function and assert result
    resp = client.call(client.MULTICALL, params, insert_secret=True)
    assert resp == expected_params


@responses.activate
def test_does_not_insert_secret_with_unknown_method_call():
    # create client with secret
    secret = "hello"
    client = JSONRPCClient(secret=secret)

    responses.add_callback(responses.POST, client.server, callback=call_params_callback)

    # create params
    params = ["param1", "param2"]

    # call function and assert result
    resp = client.call("other.method", params, insert_secret=True)
    assert secret not in resp


@responses.activate
def test_does_not_insert_secret_if_told_so():
    # create client with secret
    secret = "hello"
    client = JSONRPCClient(secret=secret)

    responses.add_callback(responses.POST, client.server, callback=call_params_callback)

    # create params
    params = ["param1", "param2"]

    # call function and assert result
    resp = client.call("other.method", params, insert_secret=False)
    assert secret not in resp


def test_client_str_returns_client_server():
    host = "https://example.com/"
    port = 7100
    client = JSONRPCClient(host, port)
    assert client.server == f"{host.rstrip('/')}:{port}/jsonrpc" == str(client)


@responses.activate
def test_batch_call():
    client = JSONRPCClient()

    responses.add_callback(responses.POST, client.server, callback=batch_call_params_callback)

    # create params
    params_1 = ["param1", "param2"]
    params_2 = ["param3", "param4"]
    # copy params and insert secret
    expected_params = [params_1, params_2]

    # call function and assert result
    resp = client.batch_call([(client.ADD_URI, params_1, 0), (client.ADD_METALINK, params_2, 1)])
    assert resp == expected_params


@responses.activate
def test_insert_secret_with_batch_call():
    # create client with secret
    secret = "hello"
    client = JSONRPCClient(secret=secret)

    responses.add_callback(responses.POST, client.server, callback=batch_call_params_callback)

    # create params
    params_1 = ["param1", "param2"]
    params_2 = ["param3", "param4"]
    # copy params and insert secret
    expected_params = [deepcopy(params_1), deepcopy(params_2)]
    for p in expected_params:
        p.insert(0, secret)

    # call function and assert result
    resp = client.batch_call([(client.ADD_URI, params_1, 0), (client.ADD_METALINK, params_2, 1)], insert_secret=True)
    assert resp == expected_params


@responses.activate
def test_multicall2():
    client = JSONRPCClient()

    responses.add_callback(responses.POST, client.server, callback=call_params_callback)

    # create params
    params_1 = ["2089b05ecca3d829"]
    params_2 = ["2fa07b6e85c40205"]
    calls = [(client.REMOVE, params_1), (client.REMOVE, params_2)]
    # copy params and insert secret
    expected_params = [
        [
            {"methodName": client.REMOVE, "params": deepcopy(params_1)},
            {"methodName": client.REMOVE, "params": deepcopy(params_2)},
        ]
    ]

    # call function and assert result
    resp = client.multicall2(calls)
    assert resp == expected_params


@responses.activate
def test_insert_secret_with_multicall2():
    # create client with secret
    secret = "hello"
    client = JSONRPCClient(secret=secret)

    responses.add_callback(responses.POST, client.server, callback=call_params_callback)

    # create params
    params_1 = ["2089b05ecca3d829"]
    params_2 = ["2fa07b6e85c40205"]
    calls = [(client.REMOVE, params_1), (client.REMOVE, params_2)]
    # copy params and insert secret
    expected_params = [
        [
            {"methodName": client.REMOVE, "params": deepcopy(params_1)},
            {"methodName": client.REMOVE, "params": deepcopy(params_2)},
        ]
    ]
    for param in expected_params[0]:
        param["params"].insert(0, secret)

    # call function and assert result
    resp = client.multicall2(calls, insert_secret=True)
    assert resp == expected_params


def test_add_metalink_method():
    # get file contents
    with open(DEBIAN_METALINK, "rb") as stream:
        metalink_contents = stream.read()
    encoded_contents = b64encode(metalink_contents).decode("utf-8")

    with Aria2Server() as server:
        assert server.client.add_metalink(encoded_contents)


def test_add_torrent_method():
    # get file contents
    with open(BUNSENLABS_TORRENT, "rb") as stream:
        torrent_contents = stream.read()
    encoded_contents = b64encode(torrent_contents).decode("utf-8")

    with Aria2Server() as server:
        assert server.client.add_torrent(encoded_contents, [])


def test_add_uri_method():
    with Aria2Server() as server:
        assert server.client.add_uri([BUNSENLABS_MAGNET])
        assert server.client.add_uri(XUBUNTU_MIRRORS)


def test_global_option_methods():
    with Aria2Server(config=CONFIGS_DIR / "max-5-dls.conf") as server:
        max_concurrent_downloads = server.client.get_global_option()["max-concurrent-downloads"]
        assert max_concurrent_downloads == "5"

        assert server.client.change_global_option({"max-concurrent-downloads": "10"}) == "OK"

        max_concurrent_downloads = server.client.get_global_option()["max-concurrent-downloads"]
        assert max_concurrent_downloads == "10"


def test_option_methods():
    with Aria2Server(session=SESSIONS_DIR / "max-dl-limit-10000.txt") as server:
        gid = server.client.tell_active(keys=["gid"])[0]["gid"]
        max_download_limit = server.client.get_option(gid=gid)["max-download-limit"]
        assert max_download_limit == "10000"

        assert server.client.change_option(gid, {"max-download-limit": "20000"}) == "OK"

        max_download_limit = server.client.get_option(gid)["max-download-limit"]
        assert max_download_limit == "20000"


def test_position_method():
    with Aria2Server(session=SESSIONS_DIR / "2-dl-in-queue.txt") as server:
        gids = server.client.tell_waiting(0, 5, keys=["gid"])
        first, second = [r["gid"] for r in gids]
        assert server.client.change_position(second, 0, "POS_SET") == 0
        assert server.client.change_position(second, 5, "POS_CUR") == 1


def test_change_uri_method():
    with Aria2Server(session=SESSIONS_DIR / "1-dl-2-uris.txt") as server:
        gid = server.client.tell_waiting(0, 1, keys=["gid"])[0]["gid"]
        assert server.client.change_uri(gid, 1, ["http://example.org/aria2"], ["http://example.org/aria3"]) == [1, 1]
        assert server.client.change_uri(gid, 1, ["http://example.org/aria3"], []) == [1, 0]


def test_force_pause_method():
    with Aria2Server(session=SESSIONS_DIR / "big-download.txt") as server:
        gid = server.client.tell_active(keys=["gid"])[0]["gid"]
        assert server.client.force_pause(gid) == gid


def test_force_pause_all_method():
    with Aria2Server(session=SESSIONS_DIR / "dl-2-aria2.txt") as server:
        assert server.client.force_pause_all() == "OK"


def test_force_remove_method():
    with Aria2Server(session=SESSIONS_DIR / "big-download.txt") as server:
        gid = server.client.tell_active(keys=["gid"])[0]["gid"]
        assert server.client.force_remove(gid)
        assert server.client.tell_status(gid, keys=["status"])["status"] == "removed"


def test_force_shutdown_method():
    with Aria2Server() as server:
        assert server.client.force_shutdown() == "OK"
        with pytest.raises(requests.ConnectionError):
            for retry in range(10):
                server.client.list_methods()
                time.sleep(1)


def test_get_files_method():
    with Aria2Server(session=SESSIONS_DIR / "dl-aria2-1.34.0.txt") as server:
        gid = server.client.tell_active(keys=["gid"])[0]["gid"]
        assert len(server.client.get_files(gid)) == 1


def test_get_global_stat_method():
    with Aria2Server() as server:
        assert server.client.get_global_stat()


def test_get_peers_method():
    with Aria2Server(session=SESSIONS_DIR / "max-dl-limit-10000.txt") as server:
        gid = server.client.tell_active(keys=["gid"])[0]["gid"]
        assert not server.client.get_peers(gid)


def test_get_servers_method():
    with Aria2Server(session=SESSIONS_DIR / "max-dl-limit-10000.txt") as server:
        gid = server.client.tell_active(keys=["gid"])[0]["gid"]
        assert server.client.get_servers(gid)


def test_get_session_info_method():
    with Aria2Server() as server:
        assert server.client.get_session_info()


def test_get_uris_method():
    with Aria2Server(session=SESSIONS_DIR / "1-dl-2-uris.txt") as server:
        gid = server.client.tell_waiting(0, 1, keys=["gid"])[0]["gid"]
        assert server.client.get_uris(gid) == [
            {"status": "waiting", "uri": "http://example.org/aria1"},
            {"status": "waiting", "uri": "http://example.org/aria2"},
        ]


def test_get_version_method():
    with Aria2Server() as server:
        assert server.client.get_version()


def test_list_methods_method():
    with Aria2Server() as server:
        assert server.client.list_methods()


def test_list_notifications_method():
    with Aria2Server() as server:
        assert server.client.list_notifications()


def test_multicall_method():
    with Aria2Server() as server:
        assert server.client.multicall(
            [[{"methodName": server.client.LIST_METHODS}, {"methodName": server.client.LIST_NOTIFICATIONS}]]
        )


def test_multicall2_method():
    with Aria2Server() as server:
        assert server.client.multicall2([(server.client.LIST_METHODS, []), (server.client.LIST_NOTIFICATIONS, [])])


def test_pause_method():
    with Aria2Server(session=SESSIONS_DIR / "dl-aria2-1.34.0.txt") as server:
        gid = server.client.tell_active(keys=["gid"])[0]["gid"]
        assert server.client.pause(gid) == gid


def test_pause_all_method():
    with Aria2Server(session=SESSIONS_DIR / "dl-2-aria2.txt") as server:
        assert server.client.pause_all() == "OK"


def test_purge_download_result_method():
    with Aria2Server() as server:
        assert server.client.purge_download_result() == "OK"


def test_remove_method():
    with Aria2Server(session=SESSIONS_DIR / "dl-aria2-1.34.0.txt") as server:
        gid = server.client.tell_active(keys=["gid"])[0]["gid"]
        assert server.client.remove(gid)
        assert server.client.tell_status(gid, keys=["status"])["status"] == "removed"


def test_remove_download_result_method():
    with Aria2Server(session=SESSIONS_DIR / "dl-aria2-1.34.0.txt") as server:
        gid = server.client.tell_active(keys=["gid"])[0]["gid"]
        server.client.remove(gid)
        assert server.client.remove_download_result(gid) == "OK"
        assert len(server.client.tell_stopped(0, 1)) == 0


def test_save_session_method():
    session_input = SESSIONS_DIR / "dl-aria2-1.34.0.txt"
    with Aria2Server(session=session_input) as server:
        session_output = server.tmp_dir / "_session.txt"
        server.client.change_global_option({"save-session": str(session_output)})
        assert server.client.save_session() == "OK"
        with open(session_input) as stream:
            input_contents = stream.read()
        with open(session_output) as stream:
            output_contents = stream.read()
        for line in input_contents.split("\n"):
            assert line in output_contents


def test_shutdown_method():
    with Aria2Server() as server:
        assert server.client.shutdown() == "OK"
        with pytest.raises(requests.ConnectionError):
            for retry in range(10):
                server.client.list_methods()
                time.sleep(1)


def test_tell_active_method():
    with Aria2Server(session=SESSIONS_DIR / "big-download.txt") as server:
        assert len(server.client.tell_active(keys=["gid"])) > 0


def test_tell_status_method():
    with Aria2Server(session=SESSIONS_DIR / "dl-aria2-1.34.0-paused.txt") as server:
        gid = server.client.tell_waiting(0, 1, keys=["gid"])[0]["gid"]
        assert server.client.tell_status(gid)


def test_tell_stopped_method():
    for retry in range(10):
        try:
            with socketserver.TCPServer(("", 8000), http.server.SimpleHTTPRequestHandler) as httpd:
                thread = Thread(target=httpd.serve_forever)
                thread.start()

                with Aria2Server(session=SESSIONS_DIR / "small-local-download.txt") as server:
                    time.sleep(1)
                    assert len(server.client.tell_stopped(0, 1, keys=["gid"])) > 0

                httpd.shutdown()
                thread.join()
        except OSError:
            time.sleep(1)
        else:
            break


def test_tell_waiting_method():
    with Aria2Server(session=SESSIONS_DIR / "2-dl-in-queue.txt") as server:
        assert server.client.tell_waiting(0, 5, keys=["gid"]) == [
            {"gid": "2089b05ecca3d829"},
            {"gid": "cca3d8292089b05e"},
        ]


def test_unpause_method():
    with Aria2Server(session=SESSIONS_DIR / "dl-aria2-1.34.0-paused.txt") as server:
        gid = server.client.tell_waiting(0, 1, keys=["gid"])[0]["gid"]
        assert server.client.unpause(gid) == gid


def test_unpause_all_method():
    with Aria2Server(session=SESSIONS_DIR / "2-dl-in-queue.txt") as server:
        assert server.client.unpause_all() == "OK"