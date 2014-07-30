angular.module('ChatController', [])
.controller('ChatController', ['$scope', '$log', '$q', '$http', '$timeout', 'state',
                               function($scope, $log, $q, $http, $timeout, state) {
   'use strict';
    $scope.state = state.state;
    $scope.hideChat = true;
    $scope.messages = [];
    $scope.state.events_from = "START";

    var shortPoll = function() {
        $http.get($scope.state.server + "/events", {
            "params": {
                "access_token" : $scope.state.access_token,
                "from" : $scope.state.events_from,
                "timeout" : 25,
            }})
            .then(function(response) {
                $scope.feedback = "Success";

                $scope.state.events_from = response.data.end;

                for (var i = 0; i < response.data.chunk.length; i++) {
                    var chunk = response.data.chunk[i];
                    if (chunk.room_id == $scope.state.room && chunk.type == "sy.room.message") {
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
        $http.put($scope.state.server + "/rooms/" + $scope.state.room + "/messages/" + $scope.state.user_id + "/" + msg_id, {
                "body": $scope.textInput,
                "msgtype": "sy.text",
            }, {
                "params" : {
                    "access_token" : $scope.state.access_token
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

    $scope.$on('loginEvent', function() {
        $scope.hideChat = false;
        $timeout(function() { document.getElementById('textInput').focus() }, 0);

        $http.put($scope.state.server + "/rooms/" + $scope.state.room + "/members/" + $scope.state.user_id + "/state", {
                "membership": "join"
            }, {
                "params" : {
                    "access_token" : $scope.state.access_token
                }
            })
            .success(function(data, status, headers, config) {
                $timeout(shortPoll, 0);
            })
            .error(function(data, status, headers, config) {
                $scope.feedback = "Can't join room: " + response.data;
                return $q.reject(response.data);
            });
    }); 
}]);