# Offset mapping: w = param_w(d) = 2.5*d + 0.5
# Solid: d_bot = -t/2, d_top = t/2
#        w_bot = -1.25*t + 0.5
#        w_top =  1.25*t + 0.5
def d_to_w(d: float) -> float:
    """Physical offset w from normalised offset d."""
    return 2.5 * d + 0.5


def t_to_w_bot(t: float) -> float:
    return d_to_w(-t / 2)


def t_to_w_top(t: float) -> float:
    return d_to_w(t / 2)


# Density <-> thickness conversion.
# Fitting: rho = a * t^b, t = (rho/a)^(1/b)
DENSITY_PARAMS = {
    "SchwarzP": {"a": 1.022,  "b": 1.092},
    "IWP":      {"a": 0.8070, "b": 1.221},
    "Gyroid":   {"a": 0.8319, "b": 1.154},
    "Diamond":  {"a": 0.5627, "b": 1.053},
}

T_MIN, T_MAX = 0.0, 0.4
SLIDER_STEPS = 1000


def t_to_rho(family: str, t: float) -> float:
    p = DENSITY_PARAMS[family]
    return p["a"] * (t ** p["b"])


def rho_to_t(family: str, rho: float) -> float:
    p = DENSITY_PARAMS[family]
    return (rho / p["a"]) ** (1.0 / p["b"])


def rho_range(family: str):
    lo = t_to_rho(family, max(T_MIN, 1e-9))
    hi = t_to_rho(family, T_MAX)
    return lo, hi


def family_from_type(t_str: str) -> str | None:
    for key in DENSITY_PARAMS:
        if t_str.startswith(key):
            return key
    return None


def t_to_slider(t: float) -> int:
    return int(round((t - T_MIN) / (T_MAX - T_MIN) * SLIDER_STEPS))


def slider_to_t(v: int) -> float:
    return T_MIN + v / SLIDER_STEPS * (T_MAX - T_MIN)


def rho_to_slider(family: str, rho: float) -> int:
    lo, hi = rho_range(family)
    v = (rho - lo) / (hi - lo) * SLIDER_STEPS
    return max(0, min(SLIDER_STEPS, int(round(v))))


def slider_to_rho(family: str, v: int) -> float:
    lo, hi = rho_range(family)
    return lo + v / SLIDER_STEPS * (hi - lo)
