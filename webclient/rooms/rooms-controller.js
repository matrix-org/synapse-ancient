'use strict';

angular.module('RoomsController', ['matrixService'])
.controller('RoomsController', ['$scope', '$location', 'matrixService',
                               function($scope, $location, matrixService) {
                                   
    $scope.rooms = [];
    $scope.public_rooms = [];
    $scope.newRoomId = "";
    $scope.feedback = "";
    
    $scope.newRoom = {
        room_id: "",
        private: false
    };
    
    $scope.goToRoom = {
        room_id: "",
    };

    $scope.newProfileInfo = {
        name: matrixService.config().displayName,
        avatar: matrixService.config().avatarUrl
    };

    $scope.linkedEmails = {
        linkNewEmail: "", // the email entry box
        emailBeingAuthed: undefined, // to populate verification text
        authTokenId: undefined, // the token id from the IS
        emailCode: "", // the code entry box
        linkedEmailList: matrixService.config().emailList // linked email list
    };

    $scope.refresh = function() {
        // List all rooms joined or been invited to
        $scope.rooms = matrixService.rooms();
        matrixService.rooms().then(
            function(data) { 
                $scope.feedback = "Success";
                $scope.rooms = data;
            },
            function(reason) {
                $scope.feedback = "Failure: " + reason;
            });
        
        matrixService.publicRooms().then(
            function(data) {
                $scope.public_rooms = data.chunk;
            }
        );
    };
    
    $scope.createNewRoom = function(room_id, isPrivate) {
        
        var visibility = "public";
        if (isPrivate) {
            visibility = "private";
        }
        
        matrixService.create(room_id, visibility).then(
            function() { 
                // This room has been created. Refresh the rooms list
                $scope.refresh();
            },
            function(reason) {
                $scope.feedback = "Failure: " + reason;
            });
    };
    
    // Go to a room
    $scope.goToRoom = function(room_id) {
        // Simply open the room page on this room id
        //$location.path("room/" + room_id);
        matrixService.join(room_id).then(
            function(response) {
                if (response.hasOwnProperty("room_id")) {
                    if (response.room_id != room_id) {
                        $location.path("room/" + response.room_id);
                        return;
                     }
                }

                $location.path("room/" + room_id);
            },
            function(reason) {
                $scope.feedback = "Can't join room: " + reason;
            }
        );
    };

    $scope.setDisplayName = function(newName) {
        matrixService.setDisplayName(newName).then(
            function(response) {
                $scope.feedback = "Updated display name.";
                var config = matrixService.config();
                config.displayName = newName;
                matrixService.setConfig(config);
                matrixService.saveConfig();
            },
            function(reason) {
                $scope.feedback = "Can't update display name: " + reason;
            }
        );
    };

    $scope.setAvatar = function(newUrl) {
        console.log("Updating avatar to "+newUrl);
        matrixService.setProfilePictureUrl(newUrl).then(
            function(response) {
                console.log("Updated avatar");
                $scope.feedback = "Updated avatar.";
                var config = matrixService.config();
                config.avatarUrl = newUrl;
                matrixService.setConfig(config);
                matrixService.saveConfig();
            },
            function(reason) {
                $scope.feedback = "Can't update avatar: " + reason;
            }
        );
    };

    $scope.linkEmail = function(email) {
        matrixService.linkEmail(email).then(
            function(response) {
                if (response.success === true) {
                    $scope.linkedEmails.authTokenId = response.tokenId;
                    $scope.emailFeedback = "You have been sent an email.";
                    $scope.linkedEmails.emailBeingAuthed = email;
                }
                else {
                    $scope.emailFeedback = "Failed to send email.";
                }
            },
            function(reason) {
                $scope.emailFeedback = "Can't send email: " + reason;
            }
        );
    };

    $scope.submitEmailCode = function(code) {
        var tokenId = $scope.linkedEmails.authTokenId;
        if (tokenId === undefined) {
            $scope.emailFeedback = "You have not requested a code with this email.";
            return;
        }
        matrixService.authEmail(matrixService.config().user_id, tokenId, code).then(
            function(response) {
                if ("success" in response && response.success === false) {
                    $scope.emailFeedback = "Failed to authenticate email.";
                    return;
                }
                var config = matrixService.config();
                var emailList = {};
                if ("emailList" in config) {
                    emailList = config.emailList;
                }
                emailList[response.address] = response;
                // save the new email list
                config.emailList = emailList;
                matrixService.setConfig(config);
                matrixService.saveConfig();
                // invalidate the email being authed and update UI.
                $scope.linkedEmails.emailBeingAuthed = undefined;
                $scope.emailFeedback = "";
                $scope.linkedEmails.linkedEmailList = emailList;
                $scope.linkedEmails.linkNewEmail = "";
                $scope.linkedEmails.emailCode = "";
            },
            function(reason) {
                $scope.emailFeedback = "Failed to auth email: " + reason;
            }
        );
    };
    
    $scope.refresh();
}]);
