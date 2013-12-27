function waitFor(ready, callback, timeout) {
    var timeoutMillis = timeout ? Math.round(timeout*1000) : 30000;
    var start = new Date().getTime();
    var condition = ready();
    var interval = setInterval(function() {
        if ((new Date().getTime() - start < timeoutMillis) && !condition ) {
            condition = ready();
        } else {
            if(!condition) {
                var message = "Timeout after "+timeoutMillis+" ms";
                console.log('{ "event": "error", "message": "'+message+'" }');
                phantom.exit(1);
            } else {
                clearInterval(interval);
                callback();
            }
        }
    }, 100);
};

function run (test) {
    var options = JSON.parse(phantom.args);
    var scheme = options.scheme ? options.scheme+'://' : 'http://';
    var host = options.host ? options.host : 'localhost';
    var port = options.port ? ':'+options.port : '';
    var path = options.path ? options.path : '/web';
    var params = [];
    if (options.action) params.push('action='+options.action);
    if (options.db) params.push('source='+options.db);
    if (options.user) params.push('login='+options.user);
    if (options.password) params.push('password='+options.password);
    var url = scheme+host+port+path+'#'+params.join('&');
    var page = require('webpage').create();
    page.viewportSize = { width: 1920, height: 1080 };
    page.onError = function(message, trace) {
        console.log('{ "event": "error", "message": "'+message+'"}');
        phantom.exit(1);
    };
    page.open(url, function (status) {
        if (status !== 'success') {
            console.log('{ "event": "failure", "message": "'+url+' failed to load"}');
            phantom.exit(1);
        } else {
            test(page);
        }
    });
}

module.exports = {
    waitFor: waitFor,
    run: run
}