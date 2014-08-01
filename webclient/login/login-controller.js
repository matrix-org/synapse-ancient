angular.module('LoginController', ['matrixService'])
.controller('LoginController', ['$scope', '$http', '$timeout', '$location', 'matrixService',
                                    function($scope, $http, $timeout, $location, matrixService) {
    'use strict';
    
    $scope.account = {
        homeserver: "", // http://matrix.openmarket.com", The hacky version of the HS hosted at the this URL does not work anymore
        user_id: "",
        access_token: ""
    };

    /*
    $scope.account.homeserver = "http://localhost:8080";
    $scope.account.user_id = "@Manu10:localhost";
    $scope.account.access_token = "QE1hbnUxMDpsb2NhbGhvc3Q..KbqazxGnAJlibDApAP";
    */


    $scope.register = function() {
        var data = {
          "user_id" : $scope.account.user_id
        };

        matrixService.setConfig({
            homeserver: $scope.account.homeserver,
        });

        $http.post($scope.account.homeserver + "/register", data).
            success(function(data, status, headers, config) {
                $scope.feedback = "Success";

                // Update the current config 
                var config = matrixService.config();
                angular.extend(config, {
                    access_token: data.access_token,
                    user_id: data.user_id                      
                });
                matrixService.setConfig(config);
                matrixService.saveConfig();

                 // Go to the user's rooms list page
                $location.path("rooms");
            }).
            error(function(data, status, headers, config) {
                var reason = data.error;
                if (!data.error) {
                    reason = JSON.stringify(data);
                }
                $scope.feedback = "Failure: " + reason;
            });
    };

    $scope.login = function() {

        matrixService.setConfig({
            homeserver: $scope.account.homeserver,
            access_token: $scope.account.access_token,
            user_id: $scope.account.user_id
        });

        // Validate the token by making a request to the HS
        $http.get($scope.account.homeserver + "/users/" + $scope.account.user_id + "/rooms/list", {
            "params": {
                "access_token" : $scope.account.access_token
            }}).
            success(function(data, status, headers, config) {

                // The request passes. We can consider to be logged in
                $scope.feedback = "Success";

                // The config is valid. Save it
                matrixService.saveConfig();

                // Go to the user's rooms list page
                $location.path("rooms");
            }).
            error(function(data, status, headers, config) {
                var reason = data.error;
                if (!data.error) {
                    reason = JSON.stringify(data);
                }
                $scope.feedback = "Failure: " + reason;
            });
    };
}]);

