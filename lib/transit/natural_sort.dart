/// Compares station names the way a person would, not the way a plain
/// string sort would: numeric prefixes compare by value ("2 Av" before
/// "14 St", not the other way round), and names starting with a digit sort
/// before names starting with a letter.
///
/// This is `stop_name` comparison only — it's a display-order convenience,
/// not a data-correctness concern.
int compareStationNames(String a, String b) {
  final aLeadingDigit = _leadingDigits(a);
  final bLeadingDigit = _leadingDigits(b);

  if (aLeadingDigit != null && bLeadingDigit != null) {
    final numCompare = aLeadingDigit.compareTo(bLeadingDigit);
    if (numCompare != 0) return numCompare;
    return a.compareTo(b);
  }
  if (aLeadingDigit != null) return -1;
  if (bLeadingDigit != null) return 1;

  return a.compareTo(b);
}

int? _leadingDigits(String s) {
  final match = RegExp(r'^\d+').firstMatch(s);
  if (match == null) return null;
  return int.parse(match.group(0)!);
}
