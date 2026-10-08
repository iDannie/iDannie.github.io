# Daniel Umeadi — Power BI project review

The portfolio now includes walkthroughs for Spotify, Business Insight 360, Apple Product Performance and Product Order Fulfilment. These describe features found in the supplied PBIX files. They do not claim verified financial results or business impact.

## Corrections in the private review copies

- Spotify: renamed the generic report page; changed Orders to Tracks in a custom chart; replaced daily-report wording with release-pattern wording.
- Apple Product: renamed the generic report page; corrected Total Quality to Total Quantity labels. Check visible card titles in Desktop.
- Product Dashboard: renamed the analytical page; fixed Product View navigation that pointed to a nonexistent page.
- Business Insight 360: removed repeated wording; clarified that Executive View is absent; replaced unsupported user-manual and support-service claims. The four analytical pages remain intact.

Only report-definition JSON is modified. ZIP integrity, unchanged binary entries and page-navigation targets are checked. Embedded data models are unchanged. These are review copies: opening, saving and checking them in Power BI Desktop remains necessary.

## Reproduce

Python 3, standard library only:

```sh
python project-source/prepare_reports.py /path/to/originals /path/to/review-output
```

Use the original filenames `spotify.pbix`, `apple product.pbix`, `Product Dashboard.pbix`, and `business_insight 360.pbix`. Originals are preserved. Changes are recorded in `changes.json` beside the review copies.

## Final Desktop checks

1. Open each review file. If Power BI rejects it, open the original and apply the listed changes in the interface instead. Save a final copy after successful validation.
2. Check slicers, navigation, bookmarks, reset actions, custom visuals and visible card labels. Product View must open Order Fulfilment.
3. Spotify: establish what Average Streams / Year and Top song vs AVG calculate. Check the calendar aggregation and default filters. Release dates are not daily listening activity.
4. Business Insight: test Finance, Sales, Marketing and Supply Chain pages. The Executive View is not implemented. Confirm dataset source and any company branding before claiming real company work.
5. Apple: verify previous-year relationships, percentage denominators, blanks and currency.
6. Product: confirm whether status percentages use quantities, rows or distinct orders.
7. Confirm dataset provenance and permission to publish the embedded data before making PBIX files publicly downloadable.
8. Export full analytical screenshots for Apple and Product, plus Finance, Sales, Marketing and Supply Chain screenshots for Business Insight.
9. Supply a verified public report URL for each project to enable interactive links. Previously shared URLs were not reliably matched to individual reports and are not guessed.

## Website and files

GitHub contains website code, descriptions and the reproducible repair script. The supplied Spotify screenshot is a static preview of the original file. Other project cards use typographic covers, not invented dashboard screenshots. The native report copies are delivered separately; Business Insight is about 325 MB and is too large for a normal GitHub repository file upload.
