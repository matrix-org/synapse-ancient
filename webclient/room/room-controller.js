angular.module('RoomController', [])
.controller('RoomController', ['$scope', '$log', '$q', '$http', '$timeout', '$routeParams', 'matrixService',
                               function($scope, $log, $q, $http, $timeout, $routeParams, matrixService) {
   'use strict';
    $scope.room_id = $routeParams.room_id;
    $scope.state = {
        user_id: matrixService.config().user_id,
        events_from: "START"
    };
    $scope.messages = [];
    
    $scope.userIDToInvite = "";

    var shortPoll = function() {
        $http.get(matrixService.config().homeserver + "/events", {
            "params": {
                "access_token": matrixService.config().access_token,
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
        
        // Send the text message
        matrixService.sendTextMessage($scope.room_id, $scope.textInput).then(
            function() {
                $scope.feedback = "Sent successfully";
                $scope.textInput = "";
            },
            function(reason) {
                $scope.feedback = "Failed to send: " + reason;
            });               
    };

    $scope.onInit = function() {
        $timeout(function() { document.getElementById('textInput').focus() }, 0);

        // Join the room
        matrixService.join($scope.room_id).then(
            function() {
                // Now start reading from the stream
                $timeout(shortPoll, 0);
            },
            function(reason) {
                $scope.feedback = "Can't join room: " + reason;
            });
    }; 
    
    $scope.inviteUser = function(user_id) {
        
        matrixService.invite($scope.room_id, user_id).then(
            function() {
                $scope.feedback = "Request for invitation succeeds";
            },
            function(reason) {
                $scope.feedback = "Failure: " + reason;
            });
    };
}]);