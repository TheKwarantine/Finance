function ajaxCheck() {

    var submit = document.getElementById("Submit");
    var form = document.getElementById("register");

    $.ajax({
        url: "/check",
        data: 'username='+$("#username").val(),
        type: "GET",

        success:function(data){
            if (data === "false") {
                return false;
            } else {
                form.submit();
            }
        }
    });
}

function liveCheck() {

    var success = document.getElementById("success");
    var failure = document.getElementById("failure");
    var un = $("#username").val();

    if (un == null || un == "") {
        failure.style.display = "none";
        success.style.display = "none";
        return false;
    }

    $.ajax({
        url: "/check",
        data: 'username='+$("#username").val(),
        type: "GET",

        success:function(data){
            if (data === "false") {
                failure.style.display = "block";
                success.style.display = "none";
                return false;
            } else {
                success.style.display = "block";
                failure.style.display = "none";
                return true;
            }
        }
    });
}