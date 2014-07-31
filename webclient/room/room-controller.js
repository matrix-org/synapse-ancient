angular.module('RoomController', [])
.controller('RoomController', ['$scope', '$log', '$q', '$http', '$timeout', '$routeParams',
                               function($scope, $log, $q, $http, $timeout, $routeParams) {
   'use strict';
    $scope.room_id = $routeParams.room_id;
    $scope.state = {
        user_id: synapseClient.getConfig().user_id,
        events_from: "START"
    };
    $scope.messages = [];
    
    $scope.newUser = {
        user_name: "",
        homeserver_name: synapseClient.getConfig().homeserver_name
    };

    var shortPoll = function() {
        $http.get(synapseClient.getConfig().homeserver_url + "/events", {
            "params": {
                "access_token": synapseClient.getConfig().access_token,
                "from": $scope.state.events_from,
                "timeout": 25000
            }})
            .then(function(response) {
                $scope.feedback = "Success";

                $scope.state.events_from = response.data.end;

                for (var i = 0; i < response.data.chunk.length; i++) {
                    var chunk = response.data.chunk[i];
                    if (chunk.room_id == $scope.room_id && chunk.type == "sy.room.message") {
                        $scope.messages.push(chunk);
                    }
                }

                $timeout(shortPoll, 0);
            }, function(response) {
                $scope.feedback = "Can't stream: " + response.data;
                $timeout(shortPoll, 1000);
            });
    };

    $scope.send = function() {
        if ($scope.textInput == "") {
            return;
        }
        var msg_id = "m" + new Date().getTime();
        $http.put(synapseClient.getConfig().homeserver_url + "/rooms/" + $scope.room_id + "/messages/" + synapseClient.getConfig().user_id + "/" + msg_id, {
                "body": $scope.textInput,
                "msgtype": "sy.text",
            }, {
                "params" : {
                    "access_token" : synapseClient.getConfig().access_token
                }
            })
            .success(function(data, status, headers, config) {
                $scope.feedback = "Sent successfully";
                $scope.textInput = "";
            })
            .error(function(data, status, headers, config) {
                $scope.feedback = "Failed to send: " + response.data;
            });                
    };

    $scope.onInit = function() {
        $timeout(function() { document.getElementById('textInput').focus() }, 0);

        $http.put(synapseClient.getConfig().homeserver_url + "/rooms/" + $scope.room_id + "/members/" + synapseClient.getConfig().user_id + "/state", {
                "membership": "join"
            }, {
                "params" : {
                    "access_token" : synapseClient.getConfig().access_token
                }
            })
            .success(function(data, status, headers, config) {
                $timeout(shortPoll, 0);
            })
            .error(function(data, status, headers, config) {
                $scope.feedback = "Can't join room: " + response.data;
                return $q.reject(response.data);
            });
    }; 
}]);