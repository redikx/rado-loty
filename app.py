from flask import Flask, redirect, render_template, request, url_for

import routes_store

app = Flask(__name__)


@app.route("/")
def routes_list():
    routes = routes_store.load_routes()
    return render_template("routes_list.html", routes=routes)


@app.route("/add", methods=["GET", "POST"])
def add_route():
    if request.method == "POST":
        errors = routes_store.validate_route(request.form)
        if errors:
            return render_template("route_form.html", route=request.form, errors=errors, action="Dodaj")
        routes_store.add_route(request.form)
        return redirect(url_for("routes_list"))
    return render_template("route_form.html", route={}, errors={}, action="Dodaj")


@app.route("/edit/<route_id>", methods=["GET", "POST"])
def edit_route(route_id):
    route = routes_store.get_route(route_id)
    if route is None:
        return redirect(url_for("routes_list"))
    if request.method == "POST":
        errors = routes_store.validate_route(request.form)
        if errors:
            return render_template("route_form.html", route=request.form, errors=errors, action="Zapisz")
        routes_store.update_route(route_id, request.form)
        return redirect(url_for("routes_list"))
    return render_template("route_form.html", route=route, errors={}, action="Zapisz")


@app.route("/delete/<route_id>", methods=["POST"])
def delete_route(route_id):
    routes_store.delete_route(route_id)
    return redirect(url_for("routes_list"))


if __name__ == "__main__":
    app.run(debug=True)
