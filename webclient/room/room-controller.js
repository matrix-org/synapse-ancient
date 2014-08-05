angular.module('RoomController', [])
.controller('RoomController', ['$scope', '$http', '$timeout', '$routeParams', 'matrixService',
                               function($scope, $http, $timeout, $routeParams, matrixService) {
   'use strict';
    $scope.room_id = $routeParams.room_id;
    $scope.state = {
        user_id: matrixService.config().user_id,
        events_from: "START"
    };
    $scope.messages = [];
    $scope.members = {};
    
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
                    else if (chunk.room_id == $scope.room_id && chunk.type == "sy.room.member") {
                        updateMemberList(chunk);
                    }
                    else if (chunk.type === "sy.presence") {
                        updatePresence(chunk);
                    }
                }

                $timeout(shortPoll, 0);
            }, function(response) {
                $scope.feedback = "Can't stream: " + response.data;
                $timeout(shortPoll, 1000);
            });
    };

    var updateMemberList = function(chunk) {
        var isNewMember = !(chunk.target_user_id in $scope.members);
        $scope.members[chunk.target_user_id] = chunk;
        if (isNewMember) {
            // get their display name and profile picture and set it to their
            // member entry in $scope.members. We HAVE to use $timeout with 0 delay 
            // to make this function run AFTER the current digest cycle, else the 
            // response may update a STALE VERSION of the member list (manifesting
            // as no member names appearing, or appearing sporadically).
            $timeout(function() {
                matrixService.getDisplayName(chunk.target_user_id).then(
                    function(response) {
                        var member = $scope.members[chunk.target_user_id];
                        if (member !== undefined) {
                            member.displayname = response.displayname;
                        }
                    }
                ); 
                matrixService.getProfilePictureUrl(chunk.target_user_id).then(
                    function(response) {
                         var member = $scope.members[chunk.target_user_id];
                         if (member !== undefined) {
                            member.avatar_url = response.avatar_url;
                         }
                    }
                );
            }, 0);
        }
    }

    var updatePresence = function(chunk) {
        if (!(chunk.content.user_id in $scope.members)) {
            console.log("updatePresence: Unknown member for chunk " + JSON.stringify(chunk));
            return;
        }
        var ONLINE = 2;
        var OFFLINE = 0;
        var member = $scope.members[chunk.content.user_id];
        if (chunk.content.state === ONLINE) {
            member.presenceState = "online";
        }
        else if (chunk.content.state === OFFLINE) {
            member.presenceState = "offline";
        }
    }

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

                // Get the current member list
                matrixService.getMemberList($scope.room_id).then(
                    function(response) {
                        for (var i = 0; i < response.chunk.length; i++) {
                            var chunk = response.chunk[i];
                            updateMemberList(chunk);
                        }
                    },
                    function(reason) {
                        $scope.feedback = "Failed get member list: " + reason;
                    }
                );
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
