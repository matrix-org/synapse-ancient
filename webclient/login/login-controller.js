angular.module('LoginController', ['matrixService'])
.controller('LoginController', ['$scope', '$location', 'matrixService',
                                    function($scope, $location, matrixService) {
    'use strict';
    
    $scope.account = {
        homeserver: "http://localhost:8080", // http://matrix.openmarket.com", The hacky version of the HS hosted at the this URL does not work anymore
        user_name_or_id: "",
        user_id: "",
        access_token: "",
        identityServer: "http://localhost:8090"
    };

    $scope.register = function() {

        // Set the urls
        matrixService.setConfig({
            homeserver: $scope.account.homeserver,
            identityServer: $scope.account.identityServer
        });

        matrixService.register($scope.account.user_name_or_id).then(
            function(data) {
                $scope.feedback = "Success";

                // Update the current config 
                var config = matrixService.config();
                angular.extend(config, {
                    access_token: data.access_token,
                    user_id: data.user_id
                });
                matrixService.setConfig(config);

                // And permanently save it
                matrixService.saveConfig();

                 // Go to the user's rooms list page
                $location.path("rooms");
            },
            function(reason) {
                $scope.feedback = "Failure: " + reason;
            });
    };

    $scope.login = function() {

        matrixService.setConfig({
            homeserver: $scope.account.homeserver,
            user_id: $scope.account.user_id,
            access_token: $scope.account.access_token
        });

        // Validate the token by making a request to the HS
        matrixService.rooms().then(
            function() {

                // The request passes. We can consider to be logged in
                $scope.feedback = "Success";

                // The config is valid. Save it
                matrixService.saveConfig();

                // Go to the user's rooms list page
                $location.path("rooms");
            },
            function(reason) {
                $scope.feedback = "Failure: " + reason;
            });
    };
}]);

